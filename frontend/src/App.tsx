import { Route, Routes, Navigate } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import DashboardPage from './pages/Dashboard';
import AgentsPage from './pages/Agents';
import ChatPage from './pages/Chat';
import PluginsPage from './pages/Plugins';
import AuditPage from './pages/Audit';

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/agents/:agentId/chat" element={<ChatPage />} />
        <Route path="/plugins" element={<PluginsPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
