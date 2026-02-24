export type UserMe = {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  created_at: string;
  last_login_at: string | null;
};

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

export type CreateAgentRequest = {
  name: string;
  provider: string;
  model: string;
  system_prompt?: string;
  temperature?: number;
  allowed_plugins?: string[] | null;
  allowed_tools?: Record<string, string[]> | null;
};

export type UpdateAgentRequest = Partial<CreateAgentRequest>;

export type ConversationSummary = {
  id: string;
  agent_id: string;
  created_at: string;
  last_message_at: string | null;
  last_message_role: string | null;
  last_message_excerpt: string | null;
  message_count: number;
};

export type ConversationMessage = {
  id: string;
  role: string;
  content: string;
  token_count: number | null;
  seq: number;
  created_at: string;
  conversation_id?: string;
};

export type ChatMessage = ConversationMessage;

export type SendMessageRequest = {
  message: string;
  conversation_id?: string | null;
};

export type SseEvent = {
  event: string;
  data: unknown;
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

export type CreatePluginRequest = never; // Backend does not support creating plugins via API yet.
