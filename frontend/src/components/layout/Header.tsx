import { AppBar, Box, IconButton, Toolbar, Typography, Stack, Avatar, Tooltip, Button, Chip } from '@mui/material';
import MenuIcon from '@mui/icons-material/MenuRounded';
import SearchIcon from '@mui/icons-material/SearchRounded';
import NotificationsIcon from '@mui/icons-material/NotificationsNoneRounded';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunchRounded';
import ShieldIcon from '@mui/icons-material/SecurityRounded';

type Props = {
  navWidth: number;
  onMenuClick: () => void;
};

export function Header({ navWidth, onMenuClick }: Props) {
  return (
    <AppBar
      position="fixed"
      color="default"
      elevation={0}
      sx={{
        borderBottom: '1px solid #E5E7EB',
        bgcolor: 'rgba(255,255,255,0.92)',
        backdropFilter: 'blur(12px)',
        width: { md: `calc(100% - ${navWidth}px)` },
        ml: { md: `${navWidth}px` },
      }}
    >
      <Toolbar sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center" sx={{ minWidth: 0 }}>
          <IconButton edge="start" color="inherit" sx={{ display: { md: 'none' } }} onClick={onMenuClick}>
            <MenuIcon />
          </IconButton>
          <Box
            sx={{
              width: 40,
              height: 40,
              borderRadius: 2,
              border: '1px solid rgba(13,148,136,0.25)',
              boxShadow: '0 12px 26px rgba(13,148,136,0.25)',
              display: 'grid',
              placeItems: 'center',
              fontWeight: 800,
              fontSize: 18,
              color: '#0D9488',
            }}
          >
            A
+          </Box>
          <Stack spacing={0.25}>
            <Typography variant="h6" fontWeight={800} color="text.primary" noWrap>
              AgentPress Runtime
            </Typography>
            <Typography variant="body2" color="text.secondary" noWrap>
              Self-hosted agents · auditable plugins
            </Typography>
          </Stack>
        </Stack>

        <Stack direction="row" spacing={1.5} alignItems="center">
          <Chip icon={<ShieldIcon />} label="Local mode" size="small" variant="outlined" sx={{ fontWeight: 700 }} />
          <Button
            startIcon={<SearchIcon />}
            sx={{
              display: { xs: 'none', sm: 'inline-flex' },
              bgcolor: '#0D9488',
              color: 'white',
              borderRadius: 999,
              px: 2.5,
              '&:hover': { bgcolor: '#0A6E64' },
            }}
          >
            Search
          </Button>
          <Tooltip title="Launch an agent chat">
            <IconButton color="primary" sx={{ bgcolor: 'rgba(13,148,136,0.08)', '&:hover': { bgcolor: 'rgba(13,148,136,0.14)' } }}>
              <RocketLaunchIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Notifications">
            <IconButton>
              <NotificationsIcon />
            </IconButton>
          </Tooltip>
          <Avatar sx={{ width: 36, height: 36, bgcolor: '#0F172A', fontWeight: 700 }}>U</Avatar>
        </Stack>
      </Toolbar>
    </AppBar>
  );
}
