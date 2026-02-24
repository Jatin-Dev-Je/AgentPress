import { useParams } from 'react-router-dom';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Stack,
  TextField,
  Typography,
  IconButton,
  InputAdornment,
  Paper,
  Avatar,
  alpha,
} from '@mui/material';
import SendIcon from '@mui/icons-material/SendRounded';
import StopIcon from '@mui/icons-material/StopRounded';
import ScienceIcon from '@mui/icons-material/ScienceRounded';
import SmartToyIcon from '@mui/icons-material/SmartToyRounded';
import PersonIcon from '@mui/icons-material/PersonRounded';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutlineRounded';
import ShieldIcon from '@mui/icons-material/SecurityRounded';
import ExtensionIcon from '@mui/icons-material/ExtensionRounded';
import FlashIcon from '@mui/icons-material/FlashOnRounded';
import { streamChat } from '../api/chat';

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  subtitle?: string;
  status?: 'running' | 'done' | 'error';
};

export default function ChatPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<() => void>();
  const assistantIdRef = useRef<string | null>(null);

  useEffect(() => {
    return () => abortRef.current?.();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages.length]);

  const roleIcon = useMemo(
    () => ({
      user: <PersonIcon fontSize="small" sx={{ color: '#34D2C5' }} />,
      assistant: <SmartToyIcon fontSize="small" sx={{ color: '#A5B4FC' }} />,
      tool: <ScienceIcon fontSize="small" sx={{ color: '#FCD34D' }} />,
    }),
    [],
  );

  function formatContent(value: unknown): string {
    if (typeof value === 'string') return value;
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value ?? '');
    }
  }

  function upsertMessage(id: string, next: Partial<ChatMessage>) {
    setMessages((prev) => {
      const exists = prev.some((m) => m.id === id);
      if (exists) return prev.map((m) => (m.id === id ? { ...m, ...next } : m));
      return [...prev, { id, role: 'assistant', content: '', ...next }];
    });
  }

  function appendToMessage(id: string, chunk: string) {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, content: `${m.content}${chunk}` } : m)));
  }

  async function send() {
    if (!agentId || !input.trim()) return;
    abortRef.current?.();
    setError(null);

    const text = input.trim();
    setInput('');
    setIsStreaming(true);

    const userId = `user-${Date.now()}`;
    const assistantId = `assistant-${Date.now()}`;
    assistantIdRef.current = assistantId;

    setMessages((prev) => [
      ...prev,
      { id: userId, role: 'user', content: text, status: 'done' },
      { id: assistantId, role: 'assistant', content: '', status: 'running' },
    ]);

    try {
      abortRef.current = await streamChat(
        agentId,
        { message: text, conversation_id: conversationId },
        (evt) => {
          if (!assistantIdRef.current) assistantIdRef.current = assistantId;
          const targetAssistantId = assistantIdRef.current;

          switch (evt.event) {
            case 'conversation':
              setConversationId((evt.data as any)?.conversation_id);
              break;
            case 'message_start':
              if (targetAssistantId) {
                upsertMessage(targetAssistantId, { status: 'running', content: '' });
              }
              break;
            case 'token': {
              const chunk = formatContent((evt.data as any)?.text ?? '');
              if (targetAssistantId) appendToMessage(targetAssistantId, chunk);
              break;
            }
            case 'message_end':
              if (targetAssistantId) upsertMessage(targetAssistantId, { status: 'done' });
              assistantIdRef.current = null;
              setIsStreaming(false);
              break;
            case 'tool_call_start': {
              const payload = evt.data as any;
              const id = payload?.tool_id || `tool-${Date.now()}`;
              upsertMessage(id, {
                id,
                role: 'tool',
                status: 'running',
                subtitle: `${payload?.plugin ?? 'plugin'} • ${payload?.tool_name ?? 'tool'}`,
                content: formatContent(payload?.params ?? {}),
              });
              break;
            }
            case 'tool_call_end': {
              const payload = evt.data as any;
              const id = payload?.tool_id || `tool-${Date.now()}`;
              upsertMessage(id, {
                role: 'tool',
                status: payload?.success ? 'done' : 'error',
                content: formatContent(payload?.result ?? payload),
              });
              break;
            }
            case 'tool_call_error': {
              const payload = evt.data as any;
              const id = payload?.tool_id || `tool-${Date.now()}`;
              upsertMessage(id, {
                role: 'tool',
                status: 'error',
                subtitle: `${payload?.plugin ?? 'plugin'} • ${payload?.tool_name ?? 'tool'}`,
                content: formatContent(payload?.error ?? 'Tool error'),
              });
              setIsStreaming(false);
              break;
            }
            case 'error': {
              const msg = formatContent((evt.data as any)?.message ?? 'Chat error');
              setError(msg);
              setIsStreaming(false);
              break;
            }
            default:
              break;
          }
        },
      );
    } catch (err) {
      setError((err as Error)?.message || 'Unable to start chat');
      setIsStreaming(false);
    }
  }

  function stop() {
    abortRef.current?.();
    assistantIdRef.current = null;
    setIsStreaming(false);
  }

  if (!agentId) {
    return <Alert severity="error">Agent ID missing in route.</Alert>;
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background:
          'radial-gradient(circle at 20% 20%, rgba(13,148,136,0.10), transparent 25%), radial-gradient(circle at 80% 10%, rgba(245,158,11,0.10), transparent 28%), linear-gradient(180deg, #0B172A 0%, #0F192D 40%, #0F212F 100%)',
        color: 'white',
      }}
    >
      <Box
        sx={{
          px: { xs: 2, md: 4 },
          py: 2.5,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 2,
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center" minWidth={0}>
          <Avatar sx={{ bgcolor: alpha('#0D9488', 0.2), color: '#34D2C5', width: 44, height: 44, fontWeight: 800 }}>
            AP
          </Avatar>
          <Stack spacing={0.25} minWidth={0}>
            <Typography variant="h6" fontWeight={800} noWrap>
              Chat Workspace
            </Typography>
            <Typography variant="body2" color="rgba(255,255,255,0.7)" noWrap>
              Streaming responses, tool calls, plugin visibility
            </Typography>
          </Stack>
          {conversationId && (
            <Chip
              label={`Conversation ${conversationId.slice(0, 8)}…`}
              size="small"
              sx={{ bgcolor: 'rgba(255,255,255,0.12)', color: 'white' }}
            />
          )}
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" justifyContent="flex-end">
          <Chip icon={<ExtensionIcon />} label="Plugins" size="small" sx={{ bgcolor: 'rgba(255,255,255,0.12)', color: 'white' }} />
          <Chip icon={<ShieldIcon />} label="Local" size="small" sx={{ bgcolor: 'rgba(255,255,255,0.12)', color: 'white' }} />
          <Chip icon={<FlashIcon />} label="Streaming" size="small" sx={{ bgcolor: 'rgba(255,255,255,0.12)', color: 'white' }} />
        </Stack>
      </Box>

      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          background: 'linear-gradient(180deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.02) 100%)',
          borderTop: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        {error && (
          <Alert severity="error" sx={{ m: 2 }} icon={<ErrorOutlineIcon fontSize="small" />}>
            {error}
          </Alert>
        )}

        <Box
          ref={scrollRef}
          sx={{
            flex: 1,
            overflowY: 'auto',
            px: { xs: 1.5, sm: 3, md: 5 },
            py: 3,
            display: 'flex',
            flexDirection: 'column',
            gap: 1.5,
          }}
        >
          {messages.map((m) => (
            <Stack
              key={m.id}
              direction="row"
              justifyContent={m.role === 'user' ? 'flex-end' : 'flex-start'}
              sx={{ width: '100%' }}
            >
              <Box
                sx={{
                  maxWidth: '860px',
                  width: '100%',
                  background:
                    m.role === 'user'
                      ? 'linear-gradient(135deg, #0D9488 0%, #34D2C5 80%)'
                      : 'rgba(255,255,255,0.04)',
                  color: m.role === 'user' ? 'white' : 'rgba(255,255,255,0.92)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 2,
                  p: 1.5,
                  boxShadow: '0 16px 40px rgba(0,0,0,0.25)',
                  backdropFilter: 'blur(6px)',
                }}
              >
                <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
                  <Stack direction="row" spacing={1} alignItems="center">
                    {roleIcon[m.role]}
                    <Typography fontWeight={700} fontSize={14}>
                      {m.role === 'user' ? 'You' : m.role === 'assistant' ? 'Assistant' : 'Tool'}
                    </Typography>
                    {m.subtitle && (
                      <Chip
                        label={m.subtitle}
                        size="small"
                        variant="outlined"
                        sx={{ borderRadius: 999, borderColor: 'rgba(255,255,255,0.3)', color: 'rgba(255,255,255,0.9)' }}
                      />
                    )}
                  </Stack>
                  {m.status === 'running' && (
                    <Chip
                      label="running"
                      size="small"
                      color="secondary"
                      sx={{ bgcolor: 'rgba(255,255,255,0.14)', color: 'white' }}
                    />
                  )}
                  {m.status === 'error' && <Chip label="error" size="small" color="error" />}
                </Stack>
                <Divider sx={{ my: 1, borderColor: 'rgba(255,255,255,0.08)' }} />
                <Typography
                  component="pre"
                  sx={{
                    m: 0,
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 13,
                  }}
                >
                  {m.content || (m.status === 'running' ? '…' : '')}
                </Typography>
              </Box>
            </Stack>
          ))}

          {isStreaming && (
            <Stack direction="row" spacing={1} alignItems="center" color="rgba(255,255,255,0.8)">
              <CircularProgress size={16} sx={{ color: '#34D2C5' }} />
              <Typography variant="body2">Streaming…</Typography>
            </Stack>
          )}
        </Box>

        <Paper
          elevation={0}
          sx={{
            borderTop: '1px solid rgba(255,255,255,0.08)',
            p: { xs: 1.5, md: 2 },
            bgcolor: 'rgba(15,23,42,0.72)',
            backdropFilter: 'blur(10px)',
            borderRadius: 0,
          }}
        >
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ xs: 'stretch', sm: 'flex-end' }}>
            <TextField
              fullWidth
              size="small"
              placeholder="Message…"
              value={input}
              multiline
              minRows={1}
              maxRows={6}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              InputProps={{
                sx: {
                  bgcolor: 'rgba(255,255,255,0.06)',
                  color: 'white',
                  borderRadius: 2,
                  '& .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(255,255,255,0.12)' },
                  '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(255,255,255,0.18)' },
                },
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      color="primary"
                      onClick={send}
                      disabled={!input.trim() || isStreaming}
                      sx={{ bgcolor: '#0D9488', color: 'white', '&:hover': { bgcolor: '#0A6E64' } }}
                    >
                      <SendIcon fontSize="small" />
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <Button
              variant="outlined"
              color="inherit"
              onClick={stop}
              disabled={!isStreaming}
              startIcon={<StopIcon fontSize="small" />}
              sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.3)' }}
            >
              Stop
            </Button>
          </Stack>
        </Paper>
      </Box>
    </Box>
  );
}
