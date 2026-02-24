import { api } from './client';
import type { Plugin } from './types';

export const pluginsApi = {
  list: async (): Promise<Plugin[]> => {
    const { data } = await api.get<Plugin[]>('/plugins');
    return data;
  },
  callTool: async (pluginId: string, toolName: string, params: Record<string, any>, agentId: string) => {
    const { data } = await api.post(`/plugins/${pluginId}/tools/${toolName}`, { params }, {
      headers: { 'X-Agent-Id': agentId },
    });
    return data;
  },
  restart: async (pluginId: string) => {
    const { data } = await api.post(`/plugins/${pluginId}/restart`);
    return data;
  },
};
