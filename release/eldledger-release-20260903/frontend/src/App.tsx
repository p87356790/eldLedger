import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { Box, Container, Typography } from "@mui/material";

import {
  fetchAccounts,
  fetchCategories,
  fetchMe,
  fetchSetupStatus,
  fetchTags,
  fetchTransactions,
  fetchUsers,
  fetchWallets,
  logout,
} from "./api/client";
import type { Account, AuthUser, Category, Tag, Transaction, WalletAccount } from "./api/client";
import { clearSession, getAccessToken, onSessionExpired } from "./api/session";
import { AccountPage } from "./components/AccountPage";
import { AccountsPage } from "./components/AccountsPage";
import { AppHeader } from "./components/AppHeader";
import { AutoRulesPage } from "./components/AutoRulesPage";
import { CategoriesPage } from "./components/CategoriesPage";
import { DataBackupPage } from "./components/DataBackupPage";
import { DashboardPage } from "./components/DashboardPage";
import { LoginPage } from "./components/LoginPage";
import { RecordsPage } from "./components/RecordsPage";
import { ReportsPage } from "./components/ReportsPage";
import { SettingsLayout } from "./components/SettingsLayout";
import { SetupPage } from "./components/SetupPage";
import { UsersPage } from "./components/UsersPage";

type BootState = "loading" | "setup" | "login" | "ready";

function AppShell({ user, onLogout }: { user: AuthUser; onLogout: () => Promise<void> }) {
  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default", pb: { xs: 4, md: 6 } }}>
      <AppHeader user={user} onLogout={onLogout} />
      <Container maxWidth="lg" sx={{ pt: { xs: 2, sm: 3 } }}>
        <Outlet />
      </Container>
    </Box>
  );
}

function App() {
  const [boot, setBoot] = useState<BootState>("loading");
  const [setupOrgName, setSetupOrgName] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [wallets, setWallets] = useState<WalletAccount[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState<boolean>(false);

  const enterApp = useCallback((user: AuthUser): void => {
    setCurrentUser(user);
    setBoot("ready");
  }, []);

  const handleLogout = useCallback(async (): Promise<void> => {
    await logout();
    clearSession();
    setCurrentUser(null);
    setBoot("login");
  }, []);

  const refresh = useCallback(async (): Promise<void> => {
    const [accountRows, categoryRows, transactionPage, walletRows, tagRows] = await Promise.all([
      fetchAccounts(),
      fetchCategories(),
      fetchTransactions(),
      fetchWallets(),
      fetchTags(),
    ]);
    setAccounts(accountRows);
    setCategories(categoryRows);
    setTransactions(transactionPage.items);
    setWallets(walletRows);
    setTags(tagRows);
  }, []);

  useEffect(() => {
    onSessionExpired(() => {
      setCurrentUser(null);
      setBoot("login");
    });
    return () => {
      onSessionExpired(null);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const bootApp = async (): Promise<void> => {
      try {
        const status = await fetchSetupStatus();
        if (cancelled) {
          return;
        }
        if (status.needs_setup) {
          setSetupOrgName(status.organization_name);
          setBoot("setup");
          return;
        }
        if (getAccessToken() === null) {
          setBoot("login");
          return;
        }
        const me = await fetchMe();
        if (!cancelled) {
          enterApp(me);
        }
      } catch {
        if (!cancelled) {
          clearSession();
          setBoot("login");
        }
      }
    };
    void bootApp();
    return () => {
      cancelled = true;
    };
  }, [enterApp]);

  useEffect(() => {
    if (boot !== "ready") {
      return;
    }
    let cancelled = false;
    const load = async (): Promise<void> => {
      try {
        await refresh();
        if (!cancelled) {
          setLoadError(null);
        }
      } catch (caught: unknown) {
        if (!cancelled) {
          setLoadError(caught instanceof Error ? caught.message : "데이터를 불러오지 못했어요.");
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [boot, refresh]);

  useEffect(() => {
    if (boot !== "ready" || currentUser?.role !== "ADMIN") {
      return;
    }
    void fetchUsers()
      .then(setUsers)
      .catch(() => setUsers([]));
  }, [boot, currentUser]);

  if (boot === "loading") {
    return (
      <Box sx={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Typography color="text.secondary">불러오는 중…</Typography>
      </Box>
    );
  }
  if (boot === "setup") {
    return <SetupPage organizationName={setupOrgName} onReady={enterApp} />;
  }
  if (boot === "login" || currentUser === null) {
    return <LoginPage onReady={enterApp} />;
  }

  return (
    <Routes>
      <Route element={<AppShell user={currentUser} onLogout={handleLogout} />}>
        <Route
          path="/"
          element={
            <RecordsPage
              accounts={accounts}
              categories={categories}
              tags={tags}
              wallets={wallets}
              transactions={transactions}
              loadError={loadError}
              importOpen={importOpen}
              onImportOpen={setImportOpen}
              onRefresh={refresh}
            />
          }
        />
        <Route
          path="/dashboard"
          element={
            <DashboardPage
              wallets={wallets}
              accounts={accounts}
              categories={categories}
              tags={tags}
              onRefresh={refresh}
            />
          }
        />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/settings" element={<SettingsLayout isAdmin={currentUser.role === "ADMIN"} />}>
          <Route index element={<Navigate to="accounts" replace />} />
          <Route
            path="accounts"
            element={<AccountsPage wallets={wallets} loadError={loadError} onRefresh={refresh} />}
          />
          <Route
            path="categories"
            element={<CategoriesPage categories={categories} tags={tags} loadError={loadError} onRefresh={refresh} />}
          />
          <Route
            path="rules"
            element={<AutoRulesPage categories={categories} tags={tags} wallets={wallets} loadError={loadError} />}
          />
          <Route path="backup" element={<DataBackupPage onImported={refresh} />} />
          <Route
            path="profile"
            element={
              <AccountPage
                user={currentUser}
                onUserChange={setCurrentUser}
                onFactoryReset={() => {
                  clearSession();
                  setCurrentUser(null);
                  setSetupOrgName("내 장부");
                  setBoot("setup");
                }}
              />
            }
          />
          <Route
            path="users"
            element={
              <UsersPage
                currentUser={currentUser}
                users={users}
                loadError={loadError}
                onRefresh={async () => {
                  setUsers(await fetchUsers());
                }}
              />
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default function AppWithRouter() {
  return (
    <BrowserRouter>
      <App />
    </BrowserRouter>
  );
}
