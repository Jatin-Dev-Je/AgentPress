import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { agentsApi } from '../api/agents';
import {
  Card,
  CardContent,
  Typography,
  Grid,
  Stack,
  Chip,
  CircularProgress,
  Alert,
  TextField,
  Box,
  Skeleton,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  MenuItem,
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import SmartToyIcon from '@mui/icons-material/SmartToyRounded';
import SearchIcon from '@mui/icons-material/SearchRounded';
import ChatIcon from '@mui/icons-material/ChatRounded';
import AddIcon from '@mui/icons-material/AddRounded';
import { useMutation, useQueryClient } from '@tanstack/react-query';

export default function AgentsPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ['agents'], queryFn: agentsApi.list });
  const queryClient = useQueryClient();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: '',
    provider: 'gemini',
    model: 'gemini-1.5-flash',
    system_prompt: '',
    temperature: 0.2,
    allowed_plugins: '',
  });
  const [submitError, setSubmitError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: async () => {
      setSubmitError(null);
      const body = {
        name: form.name.trim(),
        provider: form.provider.trim(),
        model: form.model.trim(),
        system_prompt: form.system_prompt,
        temperature: Number(form.temperature) || 0.2,
        allowed_plugins: form.allowed_plugins.trim()
          ? form.allowed_plugins.split(',').map((s) => s.trim()).filter(Boolean)
          : null,
      };
      return agentsApi.create(body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      setOpen(false);
      setForm({ name: '', provider: 'gemini', model: 'gemini-1.5-flash', system_prompt: '', temperature: 0.2, allowed_plugins: '' });
    },
    onError: (err: any) => {
      setSubmitError(err?.message || 'Failed to create agent');
    },
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    if (!q) return data;
    return data.filter((a) => a.name.toLowerCase().includes(q) || a.model.toLowerCase().includes(q));
  }, [data, query]);

  return (
    <Stack spacing={3}>
      <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems="center" spacing={2}>
        <Typography variant="h4" fontWeight={700} sx={{ alignSelf: 'flex-start' }}>Agents</Typography>
        <TextField
          size="small"
          placeholder="Search agents"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          InputProps={{ startAdornment: <SearchIcon fontSize="small" sx={{ mr: 1 }} /> }}
          sx={{ width: { xs: '100%', sm: 260 } }}
        />
        <Button startIcon={<AddIcon />} variant="contained" onClick={() => setOpen(true)} sx={{ alignSelf: 'flex-start' }}>
          New Agent
        </Button>
      </Stack>

      {isLoading && (
        <Grid container spacing={2}>
          {Array.from({ length: 6 }).map((_, i) => (
            <Grid item xs={12} sm={6} md={4} key={i}>
              <Skeleton variant="rectangular" height={140} sx={{ borderRadius: 2 }} />
            </Grid>
          ))}
        </Grid>
      )}

      {error && <Alert severity="error">{(error as Error).message}</Alert>}

      {!isLoading && !error && (
        <Grid container spacing={2}>
          {filtered.map((agent) => (
            <Grid item xs={12} sm={6} md={4} key={agent.id}>
              <Card component={RouterLink} to={`/agents/${agent.id}/chat`} sx={{ textDecoration: 'none', height: '100%' }}>
                <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Box sx={{
                      width: 36,
                      height: 36,
                      borderRadius: 1.5,
                      bgcolor: '#EEF2FF',
                      display: 'grid',
                      placeItems: 'center',
                    }}>
                      <SmartToyIcon fontSize="small" color="primary" />
                    </Box>
                    <Box>
                      <Typography variant="h6" fontWeight={700}>{agent.name}</Typography>
                      <Typography variant="body2" color="text.secondary">{agent.provider} · {agent.model}</Typography>
                    </Box>
                  </Stack>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <Chip label={`temp ${agent.temperature.toFixed(1)}`} size="small" />
                    {agent.allowed_plugins?.length ? <Chip label={`${agent.allowed_plugins.length} plugins`} size="small" variant="outlined" /> : null}
                  </Stack>
                  <Box sx={{ flexGrow: 1 }} />
                  <Button variant="outlined" size="small" startIcon={<ChatIcon fontSize="small" />} sx={{ alignSelf: 'flex-start' }}>
                    Open chat
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          ))}
          {!filtered.length && (
            <Grid item xs={12}>
              <Typography variant="body2" color="text.secondary">No agents match your search.</Typography>
            </Grid>
          )}
        </Grid>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create Agent</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, pt: 2 }}>
          {submitError && <Alert severity="error" sx={{ mb: 1 }}>{submitError}</Alert>}
          <TextField
            label="Name"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            required
          />
          <TextField
            label="Provider"
            value={form.provider}
            select
            onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value }))}
          >
            <MenuItem value="gemini">Gemini</MenuItem>
          </TextField>
          <TextField
            label="Model"
            value={form.model}
            onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
            helperText="Example: gemini-1.5-flash"
          />
          <TextField
            label="System Prompt"
            value={form.system_prompt}
            onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))}
            multiline
            minRows={2}
          />
          <TextField
            label="Temperature"
            type="number"
            inputProps={{ step: 0.1, min: 0, max: 2 }}
            value={form.temperature}
            onChange={(e) => setForm((f) => ({ ...f, temperature: parseFloat(e.target.value) }))}
          />
          <TextField
            label="Allowed Plugins (comma separated)"
            value={form.allowed_plugins}
            onChange={(e) => setForm((f) => ({ ...f, allowed_plugins: e.target.value }))}
            placeholder="echo,weather"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button onClick={() => createMutation.mutate()} disabled={createMutation.isLoading || !form.name.trim()} variant="contained">
            {createMutation.isLoading ? 'Saving…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
