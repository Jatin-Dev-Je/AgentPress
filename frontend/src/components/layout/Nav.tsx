import { NavLink } from 'react-router-dom';
import {
  Box,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/SpaceDashboardRounded';
import SmartToyIcon from '@mui/icons-material/SmartToyRounded';
import ChatIcon from '@mui/icons-material/ChatRounded';
import ExtensionIcon from '@mui/icons-material/ExtensionRounded';
import ShieldIcon from '@mui/icons-material/ShieldRounded';
import ChevronRightIcon from '@mui/icons-material/ChevronRightRounded';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeftRounded';

function LogoMark({ compact }: { compact: boolean }) {
  return (
    <Box
      sx={{
        width: compact ? 42 : 48,
        height: compact ? 42 : 48,
        borderRadius: 3,
        background: 'linear-gradient(135deg, #0D9488 0%, #22C55E 60%, #F59E0B 100%)',
        boxShadow: '0 12px 28px rgba(0,0,0,0.22)',
        display: 'grid',
        placeItems: 'center',
        color: 'white',
        fontWeight: 800,
        fontSize: compact ? 16 : 18,
        letterSpacing: '-0.03em',
      }}
    >
      AP
    </Box>
  );
}

const navItems = [
  { label: 'Dashboard', to: '/', icon: <DashboardIcon /> },
  { label: 'Agents', to: '/agents', icon: <SmartToyIcon /> },
  { label: 'Chat', to: '/agents', icon: <ChatIcon /> },
  { label: 'Plugins', to: '/plugins', icon: <ExtensionIcon /> },
  { label: 'Audit', to: '/audit', icon: <ShieldIcon /> },
];

type Props = {
  width: number;
  collapsed: boolean;
  open: boolean;
  onClose: () => void;
  onToggleCollapse: () => void;
};

export function Nav({ width, collapsed, open, onClose, onToggleCollapse }: Props) {
  const content = (
    <Box
      sx={{
        width,
        height: '100%',
        borderRight: { md: '1px solid rgba(255,255,255,0.08)', xs: '1px solid #E5E7EB' },
        bgcolor: { md: 'transparent', xs: 'white' },
        display: 'flex',
        flexDirection: 'column',
        py: 1,
        color: { md: 'rgba(255,255,255,0.9)', xs: 'inherit' },
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: collapsed ? 1.25 : 1.75,
          py: 1,
          cursor: 'pointer',
          userSelect: 'none',
          gap: 1.25,
        }}
        onClick={onToggleCollapse}
        role="button"
        aria-label="Toggle sidebar"
      >
        <Stack direction="row" spacing={1} alignItems="center" minWidth={0}>
          <LogoMark compact={collapsed} />
          {!collapsed && (
            <Stack spacing={0} minWidth={0}>
              <Typography variant="subtitle1" fontWeight={800} noWrap color="white">
                AgentPress
              </Typography>
              <Typography variant="caption" color="rgba(255,255,255,0.7)" noWrap>
                Local agent runtime
              </Typography>
            </Stack>
          )}
        </Stack>
        <Tooltip title={collapsed ? 'Expand' : 'Collapse'}>
          <IconButton size="small" sx={{ color: 'white' }}>
            {collapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
          </IconButton>
        </Tooltip>
      </Box>
      <List sx={{ flex: 1 }}>
        {navItems.map((item) => (
          <ListItemButton
            key={`${item.to}-${item.label}`}
            component={NavLink}
            to={item.to}
            onClick={onClose}
            sx={{
              gap: collapsed ? 0 : 1.5,
              px: collapsed ? 1.5 : 2,
              '&.active': {
                bgcolor: { md: 'rgba(255,255,255,0.12)', xs: '#E5E7EB' },
                color: { md: 'white', xs: '#0F172A' },
                '& .MuiListItemIcon-root': { color: { md: 'white', xs: '#0F172A' } },
              },
              '&:hover': {
                bgcolor: { md: 'rgba(255,255,255,0.08)', xs: '#F1F5F9' },
              },
            }}
          >
            <ListItemIcon sx={{ color: { md: 'rgba(255,255,255,0.65)', xs: 'text.secondary' }, minWidth: 0, mr: collapsed ? 0 : 1 }}>
              {item.icon}
            </ListItemIcon>
            {!collapsed && <ListItemText primary={item.label} />}
          </ListItemButton>
        ))}
      </List>
    </Box>
  );

  return (
    <>
      <Drawer
        variant="temporary"
        open={open}
        onClose={onClose}
        ModalProps={{ keepMounted: true }}
        sx={{ display: { xs: 'block', md: 'none' }, '& .MuiDrawer-paper': { width } }}
      >
        {content}
      </Drawer>
      <Box
        component="nav"
        sx={{
          width,
          flexShrink: 0,
          display: { xs: 'none', md: 'block' },
          position: 'fixed',
          inset: 0,
          height: '100vh',
          background: 'linear-gradient(180deg, #0B172A 0%, #0F212F 100%)',
          borderRight: '1px solid rgba(255,255,255,0.08)',
          color: 'rgba(255,255,255,0.9)',
        }}
      >
        {content}
      </Box>
    </>
  );
}
