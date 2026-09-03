import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  AppBar,
  Box,
  Button,
  Container,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";

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
import { AutoRulesPage } from "./components/AutoRulesPage";
import { CategoriesPage } from "./components/CategoriesPage";
import { ImportCsvDialog } from "./components/ImportCsvDialog";
import { LoginPage } from "./components/LoginPage";
import { SetupPage } from "./components/SetupPage";
import { TransactionForm } from "./components/TransactionForm";
import { TransactionList } from "./components/TransactionList";
import { UsersPage } from "./components/UsersPage";

type AppPage = "records" | "assets" | "categories" | "rules" | "account" | "users";
type BootState = "loading" | "setup" | "login" | "ready";

function App() {
  const [boot, setBoot] = useState<BootState>("loading");
  const [setupOrgName, setSetupOrgName] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [page, setPage] = useState<AppPage>("records");
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
    setPage("records");
  }, []);

  const handleLogout = useCallback(async (): Promise<void> => {
    await logout();
    clearSession();
    setCurrentUser(null);
    setBoot("login");
    setPage("records");
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

  const navButtonSx = {
    minHeight: 40,
    px: 1.5,
    fontSize: "0.9rem",
    color: "inherit",
  };

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
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default", pb: { xs: 4, md: 6 } }}>
      <AppBar position="sticky" elevation={0}>
        <Toolbar sx={{ gap: 1, flexWrap: "wrap" }}>
          <Box sx={{ mr: 1 }}>
            <Typography variant="h6" component="h1" sx={{ fontWeight: 800, lineHeight: 1.2 }}>
              eldLedger
            </Typography>
            <Typography variant="caption" sx={{ opacity: 0.85 }}>
              {currentUser.display_name}
            </Typography>
          </Box>
          <Button
            sx={navButtonSx}
            variant={page === "records" ? "contained" : "text"}
            color={page === "records" ? "secondary" : "inherit"}
            onClick={() => setPage("records")}
          >
            기록
          </Button>
          <Button
            sx={navButtonSx}
            variant={page === "assets" ? "contained" : "text"}
            color={page === "assets" ? "secondary" : "inherit"}
            onClick={() => setPage("assets")}
          >
            자산/계좌
          </Button>
          <Button
            sx={navButtonSx}
            variant={page === "categories" ? "contained" : "text"}
            color={page === "categories" ? "secondary" : "inherit"}
            onClick={() => setPage("categories")}
          >
            분류/태그
          </Button>
          <Button
            sx={navButtonSx}
            variant={page === "rules" ? "contained" : "text"}
            color={page === "rules" ? "secondary" : "inherit"}
            onClick={() => setPage("rules")}
          >
            자동 분류
          </Button>
          <Button
            sx={navButtonSx}
            variant={page === "account" ? "contained" : "text"}
            color={page === "account" ? "secondary" : "inherit"}
            onClick={() => setPage("account")}
          >
            내 계정
          </Button>
          {currentUser.role === "ADMIN" && (
            <Button
              sx={navButtonSx}
              variant={page === "users" ? "contained" : "text"}
              color={page === "users" ? "secondary" : "inherit"}
              onClick={() => setPage("users")}
            >
              사용자
            </Button>
          )}
          <Box sx={{ flexGrow: 1 }} />
          <Button sx={navButtonSx} color="inherit" onClick={() => void handleLogout()}>
            로그아웃
          </Button>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ pt: { xs: 2, sm: 3 } }}>
        {page === "records" ? (
          <>
            {loadError !== null && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {loadError}
              </Alert>
            )}
            <Stack direction="row" justifyContent="flex-end" sx={{ mb: 2 }}>
              <Button variant="outlined" onClick={() => setImportOpen(true)}>
                CSV 가져오기
              </Button>
            </Stack>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="flex-start">
              <Box sx={{ width: { xs: "100%", md: "58%" }, position: { md: "sticky" }, top: { md: 88 } }}>
                <TransactionForm accounts={accounts} categories={categories} tags={tags} onSaved={refresh} />
              </Box>
              <Box sx={{ width: { xs: "100%", md: "42%" } }}>
                <TransactionList transactions={transactions} accounts={accounts} categories={categories} />
              </Box>
            </Stack>
            <ImportCsvDialog
              open={importOpen}
              wallets={wallets}
              categories={categories}
              tags={tags}
              onClose={() => setImportOpen(false)}
              onImported={refresh}
            />
          </>
        ) : page === "assets" ? (
          <AccountsPage wallets={wallets} loadError={loadError} onRefresh={refresh} />
        ) : page === "categories" ? (
          <CategoriesPage categories={categories} tags={tags} loadError={loadError} onRefresh={refresh} />
        ) : page === "rules" ? (
          <AutoRulesPage categories={categories} tags={tags} wallets={wallets} loadError={loadError} />
        ) : page === "users" ? (
          <UsersPage
            currentUser={currentUser}
            users={users}
            loadError={loadError}
            onRefresh={async () => {
              setUsers(await fetchUsers());
            }}
          />
        ) : (
          <AccountPage
            user={currentUser}
            onUserChange={setCurrentUser}
            onFactoryReset={() => {
              clearSession();
              setCurrentUser(null);
              setSetupOrgName("내 장부");
              setBoot("setup");
              setPage("records");
            }}
          />
        )}
      </Container>
    </Box>
  );
}

export default App;
