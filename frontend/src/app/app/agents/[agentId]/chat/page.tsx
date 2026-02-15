import ChatClient from "./ChatClient";

export default async function ChatPage({
  params,
}: {
  params: Promise<{ agentId: string }>;
}) {
  const { agentId } = await params;
  return <ChatClient agentId={agentId} />;
}
