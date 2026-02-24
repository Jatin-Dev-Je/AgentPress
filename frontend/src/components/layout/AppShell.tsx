import { PropsWithChildren, useMemo, useState } from 'react';
import { Box, Container, Toolbar } from '@mui/material';
import { useLocation } from 'react-router-dom';
import { Header } from './Header';
import { Nav } from './Nav';

export function AppShell({ children }: PropsWithChildren) {
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();

  const isChatRoute = useMemo(() => location.pathname.startsWith('/agents/') && location.pathname.endsWith('/chat'), [location.pathname]);

  const navWidth = navCollapsed ? 78 : 240;

  return (
    <Box
      sx={{
        display: 'flex',
        minHeight: '100vh',
        background:
          'radial-gradient(circle at 15% 20%, rgba(13,148,136,0.14), transparent 30%), radial-gradient(circle at 85% 10%, rgba(245,158,11,0.18), transparent 32%), linear-gradient(135deg, #f5f7fb 0%, #eef2f8 40%, #f7fafc 100%)',
      }}
    >
      <Nav
        width={navWidth}
        collapsed={navCollapsed}
        open={navOpen}
        onClose={() => setNavOpen(false)}
        onToggleCollapse={() => setNavCollapsed((v) => !v)}
      />
      <Box
        component="main"
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          pl: { md: `${navWidth}px` },
          transition: 'padding-left 200ms ease',
        }}
      >
        {!isChatRoute && (
          <>
            <Header navWidth={navWidth} onMenuClick={() => setNavOpen(true)} />
            <Toolbar />
          </>
        )}
        <Container
          maxWidth={isChatRoute ? false : 'xl'}
          disableGutters={isChatRoute}
          sx={{
            py: isChatRoute ? 0 : 4,
            flex: 1,
            width: '100%',
            minHeight: 0,
          }}
        >
          {children}
        </Container>
      </Box>
    </Box>
  );
}
