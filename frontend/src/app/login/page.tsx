import LoginClient from "./LoginClient";

export default function LoginPage({
  searchParams,
}: {
  searchParams?: { next?: string; error?: string };
}) {
  return <LoginClient nextUrl={searchParams?.next} error={searchParams?.error} />;
}
