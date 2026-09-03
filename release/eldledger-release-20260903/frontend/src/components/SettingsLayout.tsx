import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Box, Tab, Tabs } from "@mui/material";

import { SETTINGS_NAV, SETTINGS_PATHS } from "../nav";

interface SettingsLayoutProps {
  isAdmin: boolean;
}

export function SettingsLayout({ isAdmin }: SettingsLayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const items = SETTINGS_NAV.filter((item) => !item.adminOnly || isAdmin);

  if (location.pathname === SETTINGS_PATHS.users && !isAdmin) {
    return <Navigate to={SETTINGS_PATHS.profile} replace />;
  }

  const tabValue = items.some((item) => item.path === location.pathname)
    ? location.pathname
    : SETTINGS_PATHS.accounts;

  return (
    <Box>
      <Tabs
        value={tabValue}
        onChange={(_event, value: string) => navigate(value)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ borderBottom: 1, borderColor: "divider" }}
      >
        {items.map((item) => (
          <Tab key={item.path} value={item.path} label={item.label} />
        ))}
      </Tabs>
      <Box sx={{ pt: 2 }}>
        <Outlet />
      </Box>
    </Box>
  );
}
