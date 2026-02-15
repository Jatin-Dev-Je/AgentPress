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
  model: string;
  system_prompt: string;
  temperature: number;
  allowed_plugins: string[] | null;
  allowed_tools: Record<string, string[]> | null;
  created_at: string;
  updated_at: string;
};

export type SseEvent = {
  event: string;
  data: unknown;
};
