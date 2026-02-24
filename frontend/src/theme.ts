import { createTheme } from '@mui/material/styles';

const primary = {
  main: '#0D9488',
  light: '#34D2C5',
  dark: '#0A6E64',
};

const accent = {
  main: '#F59E0B',
  light: '#FCD34D',
  dark: '#D97706',
};

export const theme = createTheme({
  typography: {
    fontFamily: '"Sora", "Plus Jakarta Sans", "Segoe UI", system-ui, -apple-system, sans-serif',
    h1: { fontWeight: 700, letterSpacing: '-0.02em' },
    h2: { fontWeight: 700, letterSpacing: '-0.02em' },
    h3: { fontWeight: 700, letterSpacing: '-0.015em' },
    button: { textTransform: 'none', fontWeight: 700, letterSpacing: '0' },
  },
  palette: {
    mode: 'light',
    primary,
    secondary: accent,
    background: {
      default: '#F3F6FB',
      paper: '#FFFFFF',
    },
    divider: '#E0E7FF',
    text: {
      primary: '#0B172A',
      secondary: '#4B5563',
    },
  },
  shape: { borderRadius: 14 },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          background: 'radial-gradient(circle at 20% 20%, rgba(13,148,136,0.08), transparent 24%), radial-gradient(circle at 80% 0%, rgba(245,158,11,0.10), transparent 26%), #F3F6FB',
        },
      },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          border: '1px solid rgba(13,148,136,0.08)',
          boxShadow: '0 24px 70px rgba(15, 23, 42, 0.08)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          fontWeight: 700,
          paddingInline: 16,
        },
        containedPrimary: {
          boxShadow: '0 12px 32px rgba(13,148,136,0.35)',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 18,
          border: '1px solid rgba(13,148,136,0.08)',
          boxShadow: '0 20px 50px rgba(15, 23, 42, 0.08)',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: { backdropFilter: 'blur(12px)' },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          margin: '4px 10px',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 700,
          letterSpacing: '-0.01em',
        },
      },
    },
  },
});
