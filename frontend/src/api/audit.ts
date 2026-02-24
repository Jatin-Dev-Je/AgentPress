import { api } from './client';
import type { ToolCallAudit } from './types';

export const auditApi = {
  toolCalls: async (limit = 200): Promise<ToolCallAudit> => {
    const { data } = await api.get<ToolCallAudit>(`/audit/tool-calls?limit=${limit}`);
    return data;
  },
};
