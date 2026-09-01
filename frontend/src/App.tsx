import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  AppBar,
  Box,
  Container,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";

import { fetchAccounts, fetchCategories, fetchTransactions } from "./api/client";
import type { Account, Category, Transaction } from "./api/client";
import { TransactionForm } from "./components/TransactionForm";
import { TransactionList } from "./components/TransactionList";

function App() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refresh = useCallback(async (): Promise<void> => {
    const [accountRows, categoryRows, transactionPage] = await Promise.all([
      fetchAccounts(),
      fetchCategories(),
      fetchTransactions(),
    ]);
    setAccounts(accountRows);
    setCategories(categoryRows);
    setTransactions(transactionPage.items);
  }, []);

  useEffect(() => {
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
  }, [refresh]);

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default", pb: { xs: 4, md: 6 } }}>
      <AppBar position="sticky" elevation={0}>
        <Toolbar>
          <Box>
            <Typography variant="h6" component="h1" sx={{ fontWeight: 800, lineHeight: 1.2 }}>
              eldLedger
            </Typography>
            <Typography variant="caption" sx={{ opacity: 0.85 }}>
              가계부처럼 기록하기
            </Typography>
          </Box>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ pt: { xs: 2, sm: 3 } }}>
        {loadError !== null && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {loadError}
          </Alert>
        )}
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="flex-start">
          <Box sx={{ width: { xs: "100%", md: "58%" }, position: { md: "sticky" }, top: { md: 88 } }}>
            <TransactionForm accounts={accounts} categories={categories} onSaved={refresh} />
          </Box>
          <Box sx={{ width: { xs: "100%", md: "42%" } }}>
            <TransactionList transactions={transactions} accounts={accounts} categories={categories} />
          </Box>
        </Stack>
      </Container>
    </Box>
  );
}

export default App;
