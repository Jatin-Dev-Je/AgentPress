import { useQuery } from '@tanstack/react-query';
import { auditApi } from '../api/audit';
import {
  Alert,
  Card,
  CardContent,
  CircularProgress,
  Stack,
  Typography,
  Divider,
  Chip,
  Grid,
  Tooltip,
} from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTimeRounded';
import ErrorIcon from '@mui/icons-material/ErrorOutlineRounded';
import CheckCircleIcon from '@mui/icons-material/CheckCircleRounded';

export default function AuditPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ['audit', 'tool-calls'], queryFn: () => auditApi.toolCalls(200) });

  if (isLoading) return <CircularProgress />;
  if (error) return <Alert severity="error">{(error as Error).message}</Alert>;

  const events = data?.events ?? [];

  return (
    <Stack spacing={3}>
      <Typography variant="h4" fontWeight={700}>Tool Call Audit</Typography>
      <Grid container spacing={2}>
        {events.map((evt) => (
          <Grid item xs={12} md={6} key={evt.id}>
            <Card>
              <CardContent>
                <Stack spacing={1.25}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography fontWeight={700}>{evt.plugin_id} • {evt.tool_name}</Typography>
                    <Chip
                      icon={evt.ok ? <CheckCircleIcon /> : <ErrorIcon />}
                      label={evt.ok ? 'OK' : 'Error'}
                      size="small"
                      color={evt.ok ? 'success' : 'error'}
                      variant={evt.ok ? 'outlined' : 'filled'}
                    />
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    Agent {evt.agent_id} · Conversation {evt.conversation_id ?? '—'} · Call {evt.tool_call_id ?? '—'}
                  </Typography>
                  <Divider />
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'JetBrains Mono, monospace' }}>
                    {JSON.stringify(evt.params, null, 2)}
                  </Typography>
                  {evt.error && (
                    <Alert severity="error" sx={{ mt: 1 }}>
                      {evt.error}
                    </Alert>
                  )}
                  <Stack direction="row" spacing={1} alignItems="center" color="text.secondary">
                    <AccessTimeIcon fontSize="small" />
                    <Tooltip title={`Started ${evt.started_at ?? 'n/a'} · Ended ${evt.ended_at ?? 'n/a'}`}>
                      <Typography variant="body2">
                        {evt.duration_ms ? `${evt.duration_ms} ms` : 'Duration n/a'}
                      </Typography>
                    </Tooltip>
                  </Stack>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        ))}
        {!events.length && (
          <Grid item xs={12}>
            <Typography variant="body2" color="text.secondary">No tool calls recorded yet.</Typography>
          </Grid>
        )}
      </Grid>
    </Stack>
  );
}
