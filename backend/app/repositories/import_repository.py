from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AutoCategoryRule, AutoCategoryRuleTag, ImportProfile, Tag


class ImportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_profiles(self, organization_id: int) -> list[ImportProfile]:
        return list(
            self._session.scalars(
                select(ImportProfile)
                .where(ImportProfile.organization_id == organization_id, ImportProfile.is_active.is_(True))
                .order_by(ImportProfile.is_preset.desc(), ImportProfile.id)
            ).all()
        )

    def get_profile(self, profile_id: int) -> ImportProfile | None:
        return self._session.get(ImportProfile, profile_id)

    def get_profile_by_preset(self, organization_id: int, preset_key: str) -> ImportProfile | None:
        return self._session.scalar(
            select(ImportProfile).where(
                ImportProfile.organization_id == organization_id,
                ImportProfile.preset_key == preset_key,
            )
        )

    def list_rules(
        self,
        organization_id: int,
        *,
        owner_user_id: int | None = None,
        active_only: bool = False,
    ) -> list[AutoCategoryRule]:
        stmt = (
            select(AutoCategoryRule)
            .options(
                selectinload(AutoCategoryRule.category),
                selectinload(AutoCategoryRule.rule_tags).selectinload(AutoCategoryRuleTag.tag),
            )
            .where(AutoCategoryRule.organization_id == organization_id)
        )
        if owner_user_id is not None:
            stmt = stmt.where(AutoCategoryRule.owner_user_id == owner_user_id)
        if active_only:
            stmt = stmt.where(AutoCategoryRule.is_active.is_(True))
        return list(self._session.scalars(stmt.order_by(AutoCategoryRule.sort_order, AutoCategoryRule.id)).all())

    def get_rule(self, rule_id: int) -> AutoCategoryRule | None:
        return self._session.scalar(
            select(AutoCategoryRule)
            .options(
                selectinload(AutoCategoryRule.category),
                selectinload(AutoCategoryRule.rule_tags).selectinload(AutoCategoryRuleTag.tag),
            )
            .where(AutoCategoryRule.id == rule_id)
        )

    def replace_rule_tags(self, rule: AutoCategoryRule, tag_ids: list[int]) -> None:
        rule.rule_tags.clear()
        seen: set[int] = set()
        for tag_id in tag_ids:
            if tag_id in seen:
                continue
            seen.add(tag_id)
            tag = self._session.get(Tag, tag_id)
            if tag is None or tag.organization_id != rule.organization_id:
                continue
            rule.rule_tags.append(AutoCategoryRuleTag(tag_id=tag_id))
