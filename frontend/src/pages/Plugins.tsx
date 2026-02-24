import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { pluginsApi } from '../api/plugins';
import {
  Alert,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  Stack,
  Typography,
  Button,
  Skeleton,
  Tooltip,
} from '@mui/material';
import RestartAltIcon from '@mui/icons-material/RestartAltRounded';
import ExtensionIcon from '@mui/icons-material/ExtensionRounded';

export default function PluginsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ['plugins'], queryFn: pluginsApi.list });

  const restartMutation = useMutation({
    mutationFn: (pluginId: string) => pluginsApi.restart(pluginId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plugins'] }),
  });

  return (
    <Stack spacing={3}>
      <Typography variant="h4" fontWeight={700}>Plugins</Typography>

      {isLoading && <CircularProgress />}
      {error && <Alert severity="error">{(error as Error).message}</Alert>}

      {!isLoading && !error && (
        <Grid container spacing={2}>
          {data?.map((plugin) => (
            <Grid item xs={12} sm={6} md={4} key={plugin.id}>
              <Card sx={{ height: '100%' }}>
                <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Chip icon={<ExtensionIcon />} label={plugin.id} size="small" variant="outlined" />
                    <Chip label={`v${plugin.version}`} size="small" />
                  </Stack>
                  <Typography variant="h6" fontWeight={700}>{plugin.name}</Typography>
                  <Typography variant="body2" color="text.secondary">{plugin.description}</Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap">
                    {plugin.tools.map((tool) => (
                      <Chip key={tool.name} label={tool.name} size="small" variant="outlined" />
                    ))}
                  </Stack>
                  <Stack direction="row" spacing={1} mt="auto">
                    <Tooltip title="Restart plugin process">
                      <span>
                        <Button
                          variant="outlined"
                          size="small"
                          startIcon={<RestartAltIcon fontSize="small" />}
                          disabled={restartMutation.isLoading}
                          onClick={() => restartMutation.mutate(plugin.id)}
                        >
                          Restart
                        </Button>
                      </span>
                    </Tooltip>
                  </Stack>
                  {restartMutation.isLoading && restartMutation.variables === plugin.id && <Skeleton height={4} />}
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Stack>
  );
}
