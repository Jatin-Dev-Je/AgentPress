// Types aligned to backend schemas
export type Agent = {
  id: string;
  name: string;
  provider: string;
  model: string;
  system_prompt: string;
  temperature: number;
  allowed_plugins: string[] | null;
  allowed_tools: Record<string, string[]> | null;
  created_at: string;
  updated_at: string;
};

export type AgentCreate = {
  name: string;
  provider: string;
  model: string;
  system_prompt?: string;
  temperature?: number;
  allowed_plugins?: string[] | null;
  allowed_tools?: Record<string, string[]> | null;
};

export type AgentUpdate = Partial<AgentCreate>;

export type Conversation = {
  id: string;
  agent_id: string;
  created_at: string;
  last_message_at: string | null;
  last_message_role: string | null;
  last_message_excerpt: string | null;
  message_count: number;
};

export type Message = {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  token_count: number | null;
  seq: number;
  created_at: string;
};

export type ChatRequest = {
  message: string;
  conversation_id?: string | null;
};

export type PluginTool = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
};

export type Plugin = {
  id: string;
  name: string;
  description: string;
  version: string;
  tools: PluginTool[];
  config_schema?: Record<string, unknown>;
};

export type ToolCallAuditEvent = {
  id: string;
  agent_id: string;
  conversation_id: string | null;
  tool_call_id: string | null;
  plugin_id: string;
  tool_name: string;
  params: Record<string, any>;
  ok: boolean;
  response: any;
  error: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number;
  created_at: string | null;
};

export type ToolCallAudit = {
  events: ToolCallAuditEvent[];
};
