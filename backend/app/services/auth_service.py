from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.init_db import DEFAULT_ORGANIZATION_NAME
from app.db.reset import CONFIRM_PHRASE, reset_all_data
from app.models import AuditLog, Organization, RefreshToken, User
from app.models.enums import UserRole
from app.repositories.user_repository import UserRepository
from app.services.chart_template_service import ChartTemplateService
from app.schemas.auth import (
    AuthResponse,
    FactoryResetRequest,
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    SetupCreate,
    SetupStatus,
    TokenPair,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token, create_refresh_token, decode_token
from app.services.accounting_service import AccountingError
from app.services.audit_service import AuditService


class AuthService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._audit = AuditService(session)
        self._charts = ChartTemplateService(session)

    def setup_status(self) -> SetupStatus:
        organization = self._session.scalar(select(Organization).order_by(Organization.id))
        return SetupStatus(
            needs_setup=self._users.count() == 0,
            organization_name=organization.name if organization is not None else DEFAULT_ORGANIZATION_NAME,
        )

    def factory_reset(self, actor: User, payload: FactoryResetRequest) -> SetupStatus:
        if payload.confirm.strip() != CONFIRM_PHRASE:
            raise AccountingError(f'확인을 위해 "{CONFIRM_PHRASE}"를 입력해 주세요.')
        if not verify_password(payload.password, actor.hashed_password):
            raise AccountingError("비밀번호가 올바르지 않아요.")
        reset_all_data(self._session)
        self._session.flush()
        return self.setup_status()

    def complete_setup(self, payload: SetupCreate) -> AuthResponse:
        if self._users.count() > 0:
            raise AccountingError("이미 초기 설정이 완료되었어요.")
        organization = self._session.scalar(select(Organization).order_by(Organization.id))
        if organization is None:
            organization = self._charts.create_ledger(DEFAULT_ORGANIZATION_NAME).organization
        else:
            self._charts.clone_into(organization)
        self._session.flush()
        user = self._create_user(
            organization_id=organization.id,
            username=payload.username,
            email=payload.email,
            display_name=payload.display_name,
            password=payload.password,
            role=UserRole.ADMIN,
        )
        self._charts.provision_user_ledger(user)
        self._audit.record(action="SETUP", user_id=user.id, entity_type="user", entity_id=user.id, details="첫 관리자 계정 생성")
        return self._issue_session(user, action="LOGIN")

    def login(self, payload: LoginRequest) -> AuthResponse:
        user = self._users.find_login(payload.username)
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise AccountingError("사용자명 또는 비밀번호가 올바르지 않아요.")
        if not user.is_active:
            raise AccountingError("비활성화된 계정이에요. 관리자에게 문의해 주세요.")
        return self._issue_session(user, action="LOGIN")

    def refresh(self, refresh_token: str) -> TokenPair:
        user, stored = self._require_refresh(refresh_token)
        stored.revoked_at = datetime.now(timezone.utc)
        self._session.flush()
        access, refresh, _user = self._mint(user)
        return TokenPair(access_token=access, refresh_token=refresh, expires_in=settings.access_token_minutes * 60)

    def logout(self, user: User, refresh_token: str | None) -> None:
        if refresh_token:
            try:
                _user, stored = self._require_refresh(refresh_token)
                stored.revoked_at = datetime.now(timezone.utc)
            except AccountingError:
                pass
        self._audit.record(action="LOGOUT", user_id=user.id, entity_type="user", entity_id=user.id)
        self._session.flush()

    def list_users(self, actor: User) -> list[UserRead]:
        return [UserRead.model_validate(item) for item in self._users.list_for_organization(actor.organization_id)]

    def create_user(self, actor: User, payload: UserCreate) -> UserRead:
        user = self._create_user(
            organization_id=actor.organization_id,
            username=payload.username,
            email=payload.email,
            display_name=payload.display_name,
            password=payload.password,
            role=payload.role,
        )
        self._charts.provision_user_ledger(user)
        self._audit.record(
            action="USER_CREATE",
            user_id=actor.id,
            entity_type="user",
            entity_id=user.id,
            details=f"{user.username} 추가 ({user.role.value})",
        )
        return UserRead.model_validate(user)

    def update_user(self, actor: User, user_id: int, payload: UserUpdate) -> UserRead:
        user = self._require_org_user(actor, user_id)
        if payload.display_name is not None:
            user.display_name = payload.display_name.strip()
        if payload.email is not None:
            self._assert_email_free(payload.email, exclude_id=user.id)
            user.email = payload.email.strip().lower()
        if payload.role is not None and payload.role != user.role:
            if user.role == UserRole.ADMIN and payload.role != UserRole.ADMIN:
                self._assert_not_last_admin(user)
            user.role = payload.role
        if payload.is_active is not None:
            self._set_active(actor, user, payload.is_active)
        self._session.flush()
        self._audit.record(action="USER_UPDATE", user_id=actor.id, entity_type="user", entity_id=user.id, details=user.username)
        return UserRead.model_validate(user)

    def deactivate_user(self, actor: User, user_id: int) -> UserRead:
        user = self._require_org_user(actor, user_id)
        self._set_active(actor, user, False)
        self._session.flush()
        self._audit.record(action="USER_DEACTIVATE", user_id=actor.id, entity_type="user", entity_id=user.id, details=user.username)
        return UserRead.model_validate(user)

    def update_profile(self, user: User, payload: ProfileUpdate) -> UserRead:
        if payload.display_name is not None:
            user.display_name = payload.display_name.strip()
        if payload.email is not None:
            self._assert_email_free(payload.email, exclude_id=user.id)
            user.email = payload.email.strip().lower()
        self._session.flush()
        self._audit.record(action="PROFILE_UPDATE", user_id=user.id, entity_type="user", entity_id=user.id)
        return UserRead.model_validate(user)

    def change_password(self, user: User, payload: PasswordChange) -> None:
        if not verify_password(payload.current_password, user.hashed_password):
            raise AccountingError("현재 비밀번호가 올바르지 않아요.")
        if payload.current_password == payload.new_password:
            raise AccountingError("새 비밀번호는 지금과 달라야 해요.")
        user.hashed_password = hash_password(payload.new_password)
        for token in user.refresh_tokens:
            if token.revoked_at is None:
                token.revoked_at = datetime.now(timezone.utc)
        self._audit.record(action="PASSWORD_CHANGE", user_id=user.id, entity_type="user", entity_id=user.id)
        self._session.flush()

    def login_history(self, user: User, *, limit: int = 20) -> list[AuditLog]:
        return list(
            self._session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.user_id == user.id,
                    AuditLog.action.in_(("LOGIN", "LOGOUT", "PASSWORD_CHANGE", "SETUP")),
                )
                .order_by(AuditLog.id.desc())
                .limit(limit)
            ).all()
        )

    def _create_user(
        self,
        *,
        organization_id: int,
        username: str,
        email: str,
        display_name: str,
        password: str,
        role: UserRole,
    ) -> User:
        cleaned_username = username.strip()
        cleaned_email = email.strip().lower()
        if self._users.get_by_username(cleaned_username) is not None:
            raise AccountingError("이미 쓰는 사용자명이에요.")
        if self._users.get_by_email(cleaned_email) is not None:
            raise AccountingError("이미 쓰는 이메일이에요.")
        if "@" not in cleaned_email or "." not in cleaned_email.split("@")[-1]:
            raise AccountingError("이메일 형식을 확인해 주세요.")
        user = User(
            organization_id=organization_id,
            username=cleaned_username,
            email=cleaned_email,
            hashed_password=hash_password(password),
            display_name=display_name.strip(),
            role=role,
            is_active=True,
        )
        self._session.add(user)
        self._session.flush()
        return user

    def _issue_session(self, user: User, *, action: str) -> AuthResponse:
        access, refresh, user = self._mint(user)
        user.last_login_at = datetime.now(timezone.utc)
        self._audit.record(action=action, user_id=user.id, entity_type="user", entity_id=user.id)
        self._session.flush()
        return AuthResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.access_token_minutes * 60,
            user=UserRead.model_validate(user),
        )

    def _mint(self, user: User) -> tuple[str, str, User]:
        access = create_access_token(user_id=user.id, organization_id=user.organization_id, role=user.role.value)
        refresh, jti, expires_at = create_refresh_token(user_id=user.id)
        self._session.add(RefreshToken(user_id=user.id, jti=jti, expires_at=expires_at))
        self._session.flush()
        return access, refresh, user

    def _require_refresh(self, refresh_token: str) -> tuple[User, RefreshToken]:
        try:
            payload = decode_token(refresh_token, "refresh")
            jti = str(payload["jti"])
            user_id = int(payload["sub"])
        except Exception as error:
            raise AccountingError("다시 로그인해 주세요.") from error
        stored = self._users.get_refresh(jti)
        if stored is None or stored.revoked_at is not None:
            raise AccountingError("다시 로그인해 주세요.")
        if stored.expires_at.replace(tzinfo=stored.expires_at.tzinfo or timezone.utc) < datetime.now(timezone.utc):
            raise AccountingError("다시 로그인해 주세요.")
        user = self._users.get(user_id)
        if user is None or not user.is_active or stored.user_id != user.id:
            raise AccountingError("다시 로그인해 주세요.")
        return user, stored

    def _require_org_user(self, actor: User, user_id: int) -> User:
        user = self._users.get(user_id)
        if user is None or user.organization_id != actor.organization_id:
            raise LookupError("사용자를 찾을 수 없습니다.")
        return user

    def _assert_email_free(self, email: str, *, exclude_id: int) -> None:
        existing = self._users.get_by_email(email.strip().lower())
        if existing is not None and existing.id != exclude_id:
            raise AccountingError("이미 쓰는 이메일이에요.")

    def _assert_not_last_admin(self, user: User) -> None:
        if user.role == UserRole.ADMIN and self._users.admin_count(user.organization_id, exclude_id=user.id) == 0:
            raise AccountingError("마지막 관리자는 권한을 바꿀 수 없어요.")

    def _set_active(self, actor: User, user: User, is_active: bool) -> None:
        if actor.id == user.id and not is_active:
            raise AccountingError("자기 계정은 비활성화할 수 없어요.")
        if user.role == UserRole.ADMIN and not is_active:
            self._assert_not_last_admin(user)
        user.is_active = is_active
        if not is_active:
            now = datetime.now(timezone.utc)
            for token in user.refresh_tokens:
                if token.revoked_at is None:
                    token.revoked_at = now
