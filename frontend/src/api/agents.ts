import { api } from './client';
import type { Agent, AgentCreate, AgentUpdate, Conversation, Message } from './types';

export const agentsApi = {
  list: async (): Promise<Agent[]> => {
    const { data } = await api.get<Agent[]>('/agents');
    return data;
  },
  get: async (id: string): Promise<Agent> => {
    const { data } = await api.get<Agent>(`/agents/${id}`);
    return data;
  },
  create: async (body: AgentCreate): Promise<Agent> => {
    const { data } = await api.post<Agent>('/agents', body);
    return data;
  },
  update: async (id: string, body: AgentUpdate): Promise<Agent> => {
    const { data } = await api.put<Agent>(`/agents/${id}`, body);
    return data;
  },
  remove: async (id: string): Promise<void> => {
    await api.delete(`/agents/${id}`);
  },
  conversations: async (agentId: string): Promise<Conversation[]> => {
    const { data } = await api.get<Conversation[]>(`/agents/${agentId}/conversations`);
    return data;
  },
  messages: async (agentId: string, conversationId: string): Promise<Message[]> => {
    const { data } = await api.get<Message[]>(`/agents/${agentId}/conversations/${conversationId}/messages`);
    return data;
  },
};
