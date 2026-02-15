import LoginClient from "./LoginClient";

export default async function LoginPage({
  searchParams,
}: {
  searchParams?: Promise<{ next?: string; error?: string }>;
}) {
  const sp = (await searchParams) || {};
  return <LoginClient nextUrl={sp.next} error={sp.error} />;
}
