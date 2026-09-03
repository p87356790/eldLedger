import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#1565c0",
    },
    secondary: {
      main: "#2e7d32",
    },
    background: {
      default: "#f5f7fb",
    },
  },
  typography: {
    fontFamily: '"Pretendard", "Noto Sans KR", "Malgun Gothic", sans-serif',
    button: {
      fontWeight: 700,
    },
  },
  shape: {
    borderRadius: 14,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          minHeight: 52,
          fontSize: "1.05rem",
          textTransform: "none",
        },
      },
    },
    MuiToggleButton: {
      styleOverrides: {
        root: {
          minHeight: 48,
          fontSize: "0.95rem",
          textTransform: "none",
          fontWeight: 700,
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          minHeight: 56,
          fontSize: "0.95rem",
          fontWeight: 700,
          textTransform: "none",
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        fullWidth: true,
      },
    },
    MuiFormControl: {
      defaultProps: {
        fullWidth: true,
      },
    },
  },
});
