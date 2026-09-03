import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import LogoutIcon from "@mui/icons-material/Logout";
import MenuIcon from "@mui/icons-material/Menu";
import SettingsIcon from "@mui/icons-material/Settings";
import {
  AppBar,
  Box,
  Button,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  Menu,
  MenuItem,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";

import type { AuthUser } from "../api/client";
import { isSettingsPath, MAIN_NAV, SETTINGS_NAV } from "../nav";

interface AppHeaderProps {
  user: AuthUser;
  onLogout: () => Promise<void>;
}

const navButtonSx = {
  minHeight: 40,
  px: 1.5,
  fontSize: "0.9rem",
  color: "inherit",
};

export function AppHeader({ user, onLogout }: AppHeaderProps) {
  const theme = useTheme();
  const compact = useMediaQuery(theme.breakpoints.down("md"));
  const location = useLocation();
  const navigate = useNavigate();
  const [settingsEl, setSettingsEl] = useState<HTMLElement | null>(null);
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const isAdmin = user.role === "ADMIN";
  const settingsOpen = settingsEl !== null;
  const visibleSettings = SETTINGS_NAV.filter((item) => !item.adminOnly || isAdmin);

  const go = (path: string): void => {
    navigate(path);
    setSettingsEl(null);
    setDrawerOpen(false);
  };

  const handleLogout = (): void => {
    setSettingsEl(null);
    setDrawerOpen(false);
    void onLogout();
  };

  return (
    <>
      <AppBar position="sticky" elevation={0}>
        <Toolbar sx={{ gap: 1, minHeight: { xs: 64, md: 72 } }}>
          <Box sx={{ mr: { xs: 0, md: 1 }, minWidth: 0 }}>
            <Typography variant="h6" component="h1" sx={{ fontWeight: 800, lineHeight: 1.2 }}>
              eldLedger
            </Typography>
            <Typography variant="caption" sx={{ opacity: 0.85, display: "block" }} noWrap>
              {user.display_name}
            </Typography>
          </Box>

          {!compact &&
            MAIN_NAV.map((item) => {
              const selected = item.path === "/" ? location.pathname === "/" : location.pathname.startsWith(item.path);
              return (
                <Button
                  key={item.path}
                  sx={navButtonSx}
                  variant={selected ? "contained" : "text"}
                  color={selected ? "secondary" : "inherit"}
                  onClick={() => go(item.path)}
                >
                  {item.label}
                </Button>
              );
            })}

          <Box sx={{ flexGrow: 1 }} />

          {compact ? (
            <IconButton color="inherit" aria-label="메뉴 열기" onClick={() => setDrawerOpen(true)}>
              <MenuIcon />
            </IconButton>
          ) : (
            <>
              <Button
                sx={navButtonSx}
                variant={isSettingsPath(location.pathname) ? "contained" : "text"}
                color={isSettingsPath(location.pathname) ? "secondary" : "inherit"}
                startIcon={<SettingsIcon />}
                aria-haspopup="true"
                aria-expanded={settingsOpen}
                onClick={(event) => setSettingsEl(event.currentTarget)}
              >
                설정
              </Button>
              <Menu
                anchorEl={settingsEl}
                open={settingsOpen}
                onClose={() => setSettingsEl(null)}
                anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
                transformOrigin={{ vertical: "top", horizontal: "right" }}
              >
                {visibleSettings.map((item) => (
                  <MenuItem
                    key={item.path}
                    selected={location.pathname === item.path}
                    onClick={() => go(item.path)}
                  >
                    {item.label}
                  </MenuItem>
                ))}
              </Menu>
              <Button sx={navButtonSx} color="inherit" startIcon={<LogoutIcon />} onClick={handleLogout}>
                로그아웃
              </Button>
            </>
          )}
        </Toolbar>
      </AppBar>

      <Drawer anchor="right" open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <Box sx={{ width: 280, py: 1 }} role="presentation">
          <Typography sx={{ px: 2, py: 1.5, fontWeight: 800 }}>메뉴</Typography>
          <List>
            {MAIN_NAV.map((item) => {
              const selected = item.path === "/" ? location.pathname === "/" : location.pathname.startsWith(item.path);
              return (
                <ListItemButton key={item.path} selected={selected} onClick={() => go(item.path)}>
                  <ListItemText primary={item.label} />
                </ListItemButton>
              );
            })}
          </List>
          <Divider />
          <Typography sx={{ px: 2, pt: 1.5, pb: 0.5, fontWeight: 700, color: "text.secondary" }}>설정</Typography>
          <List>
            {visibleSettings.map((item) => (
              <ListItemButton
                key={item.path}
                selected={location.pathname === item.path}
                onClick={() => go(item.path)}
              >
                <ListItemText primary={item.label} />
              </ListItemButton>
            ))}
          </List>
          <Divider />
          <List>
            <ListItemButton onClick={handleLogout}>
              <ListItemText primary="로그아웃" />
            </ListItemButton>
          </List>
        </Box>
      </Drawer>
    </>
  );
}
