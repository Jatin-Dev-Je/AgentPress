import { useQuery } from '@tanstack/react-query';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Stack,
  Skeleton,
  Chip,
  Divider,
  Box,
  Button,
  Avatar,
  LinearProgress,
} from '@mui/material';
import ArrowOutwardIcon from '@mui/icons-material/ArrowOutwardRounded';
import ShieldIcon from '@mui/icons-material/SecurityRounded';
import FlashIcon from '@mui/icons-material/FlashOnRounded';
import ExtensionIcon from '@mui/icons-material/ExtensionRounded';
import { agentsApi } from '../api/agents';
import { pluginsApi } from '../api/plugins';
import { auditApi } from '../api/audit';

export default function DashboardPage() {
  const agentsQuery = useQuery({ queryKey: ['agents'], queryFn: agentsApi.list });
  const pluginsQuery = useQuery({ queryKey: ['plugins'], queryFn: pluginsApi.list });
  const auditQuery = useQuery({ queryKey: ['audit', 'tool-calls'], queryFn: () => auditApi.toolCalls(20) });

  const loading = agentsQuery.isLoading || pluginsQuery.isLoading || auditQuery.isLoading;

  const stats = [
    { label: 'Agents', value: agentsQuery.data?.length ?? 0 },
    { label: 'Plugins', value: pluginsQuery.data?.length ?? 0 },
    { label: 'Tool Calls (24h)', value: auditQuery.data?.events.length ?? 0 },
    { label: 'Uptime', value: '99.9%' },
  ];

  const recentEvents = (auditQuery.data?.events ?? []).slice(0, 5);

  return (
    <Stack spacing={3}>
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <Card
            sx={{
              position: 'relative',
              overflow: 'hidden',
              background: 'linear-gradient(135deg, #0D9488 0%, #0F766E 45%, #0B172A 100%)',
              color: 'white',
              border: '1px solid rgba(255,255,255,0.18)',
            }}
          >
            <Box sx={{ position: 'absolute', inset: 0, background: 'radial-gradient(circle at 20% 20%, rgba(255,255,255,0.1), transparent 35%)' }} />
            <CardContent sx={{ position: 'relative', zIndex: 1 }}>
              <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" alignItems={{ xs: 'flex-start', md: 'center' }} spacing={2}>
                <Stack spacing={1} maxWidth={{ xs: '100%', md: '60%' }}>
                  <Chip label="Live" color="secondary" size="small" sx={{ alignSelf: 'flex-start', bgcolor: 'rgba(255,255,255,0.16)', color: 'white' }} />
                  <Typography variant="h3" fontWeight={800} letterSpacing="-0.02em">
                    AgentPress Ops Console
                  </Typography>
                  <Typography variant="body1" sx={{ opacity: 0.9 }}>
                    Observe agents, stream chats, and audit every tool call in one place. Built for self-hosted, auditable AI operations.
                  </Typography>
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} mt={1}>
                    <Button variant="contained" color="secondary" endIcon={<ArrowOutwardIcon />} href="/agents">
                      Create agent
                    </Button>
                    <Button variant="outlined" color="inherit" endIcon={<ExtensionIcon />}
                      href="/plugins"
                      sx={{ borderColor: 'rgba(255,255,255,0.4)', color: 'white', '&:hover': { borderColor: 'white', bgcolor: 'rgba(255,255,255,0.08)' } }}
                    >
                      View plugins
                    </Button>
                  </Stack>
                </Stack>
                <Stack spacing={1.5} sx={{ minWidth: { md: 260 } }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Avatar sx={{ bgcolor: 'rgba(255,255,255,0.14)' }}>
                      <ShieldIcon />
                    </Avatar>
                    <Stack spacing={0.25}>
                      <Typography variant="subtitle2" sx={{ opacity: 0.8 }}>Auditability</Typography>
                      <Typography variant="h6" fontWeight={800}>Full tool visibility</Typography>
                    </Stack>
                  </Box>
                  <LinearProgress variant="determinate" value={82} sx={{ height: 8, borderRadius: 999, bgcolor: 'rgba(255,255,255,0.18)', '& .MuiLinearProgress-bar': { bgcolor: '#FCD34D' } }} />
                  <Stack direction="row" spacing={1}>
                    <Chip icon={<FlashIcon />} label="Streaming ready" sx={{ bgcolor: 'rgba(255,255,255,0.12)', color: 'white' }} />
                    <Chip label="Local-first" sx={{ bgcolor: 'rgba(255,255,255,0.12)', color: 'white' }} />
                  </Stack>
                </Stack>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        {stats.map((stat) => (
          <Grid item xs={12} sm={6} md={3} key={stat.label}>
            <Card>
              <CardContent>
                <Typography variant="overline" color="text.secondary">{stat.label}</Typography>
                {loading ? <Skeleton width={60} /> : <Typography variant="h5" fontWeight={700}>{stat.value}</Typography>}
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1.5}>
                <Typography variant="h6" fontWeight={700}>Agents</Typography>
                <Chip label={`${agentsQuery.data?.length ?? 0} total`} size="small" />
              </Stack>
              <Stack spacing={1}>
                {loading && Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} height={40} />
                ))}
                {!loading && (agentsQuery.data ?? []).map((agent) => (
                  <Stack key={agent.id} direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 1.25, border: '1px solid #E5E7EB', borderRadius: 2 }}>
                    <Box>
                      <Typography fontWeight={700}>{agent.name}</Typography>
                      <Typography variant="body2" color="text.secondary">{agent.provider} · {agent.model}</Typography>
                    </Box>
                    <Chip label={`temp ${agent.temperature.toFixed(1)}`} size="small" />
                  </Stack>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1.5}>
                <Typography variant="h6" fontWeight={700}>Recent Tool Calls</Typography>
                <Chip label={`${recentEvents.length} shown`} size="small" />
              </Stack>
              <Stack spacing={1.25}>
                {loading && Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} height={50} />
                ))}
                {!loading && recentEvents.map((evt) => (
                  <Box key={evt.id} sx={{ p: 1.25, border: '1px solid #E5E7EB', borderRadius: 2 }}>
                    <Stack direction="row" justifyContent="space-between" alignItems="center" mb={0.5}>
                      <Typography fontWeight={700}>{evt.plugin_id} • {evt.tool_name}</Typography>
                      <Chip label={evt.ok ? 'OK' : 'Error'} size="small" color={evt.ok ? 'success' : 'error'} />
                    </Stack>
                    <Typography variant="body2" color="text.secondary">
                      Agent {evt.agent_id} · {evt.conversation_id ?? 'no convo'}
                    </Typography>
                  </Box>
                ))}
                {!loading && recentEvents.length === 0 && (
                  <Typography variant="body2" color="text.secondary">No tool calls yet.</Typography>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Stack>
  );
}
