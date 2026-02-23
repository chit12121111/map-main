import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { API_BASE_URL, api } from "../lib/api";
import { Badge, Button, Card, Input, PageHeader } from "../components/ui";

export default function SettingsPage() {
  const [email, setEmail] = useState("");
  const [expires, setExpires] = useState(7);
  const tokensQ = useQuery({ queryKey: ["tokens"], queryFn: () => api.getTokens() });
  const checkinsQ = useQuery({ queryKey: ["checkins"], queryFn: () => api.getCheckins() });
  const responsesQ = useQuery({ queryKey: ["responses"], queryFn: () => api.getResponses() });
  const clearMutation = useMutation({ mutationFn: api.clearAll });
  const tokenMutation = useMutation({ mutationFn: ({ e, d }: { e: string; d: number }) => api.createToken(e, d) });

  const onCreateToken = (ev: FormEvent) => {
    ev.preventDefault();
    if (!email.trim()) return;
    tokenMutation.mutate({ e: email, d: expires });
  };

  const apiLoginUrl = `${API_BASE_URL}/login`;
  const googleOAuthUrl = (() => {
    const direct = (import.meta.env.VITE_GOOGLE_OAUTH_URL as string | undefined)?.trim();
    if (direct) return direct;
    const clientId = (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined)?.trim();
    if (!clientId) return "";
    const redirectUri =
      (import.meta.env.VITE_GOOGLE_REDIRECT_URI as string | undefined)?.trim() ||
      (typeof window !== "undefined" ? `${window.location.origin}/` : "http://localhost:5173/");
    const params = new URLSearchParams({
      client_id: clientId,
      redirect_uri: redirectUri,
      response_type: "code",
      scope: "https://www.googleapis.com/auth/gmail.send",
      access_type: "offline",
      prompt: "consent",
    });
    return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
  })();

  return (
    <div className="page-stack">
      <PageHeader title="Settings" subtitle="System / Check-in / Environment" right={<Badge tone="neutral">API: {API_BASE_URL}</Badge>} />

      <div className="split-grid">
        <Card title="Login Integrations">
          <div className="column gap-sm">
            <div className="row gap-sm">
              <Button variant="secondary" onClick={() => window.open(apiLoginUrl, "_blank", "noopener,noreferrer")}>
                Login API
              </Button>
              <Badge tone="info">URL: {apiLoginUrl}</Badge>
            </div>

            <div className="row gap-sm">
              <Button
                variant="primary"
                onClick={() => window.open(googleOAuthUrl, "_blank", "noopener,noreferrer")}
                disabled={!googleOAuthUrl}
              >
                Login Gmail
              </Button>
              <Badge tone={googleOAuthUrl ? "ok" : "warn"}>{googleOAuthUrl ? "Google OAuth Ready" : "Set VITE_GOOGLE_CLIENT_ID"}</Badge>
            </div>
          </div>
        </Card>

        <Card title="System Actions">
          <Button variant="danger" onClick={() => clearMutation.mutate()} disabled={clearMutation.isPending}>
            {clearMutation.isPending ? "Clearing..." : "Clear places/emails/urls"}
          </Button>
          {clearMutation.data ? <p>{clearMutation.data.message}</p> : null}
        </Card>

        <Card title="Create check-in token">
          <form className="runner-form" onSubmit={onCreateToken}>
            <label>
              Email
              <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" />
            </label>
            <label>
              Expires in days
              <Input type="number" min={1} value={expires} onChange={(e) => setExpires(Number(e.target.value))} />
            </label>
            <Button variant="primary" type="submit" disabled={tokenMutation.isPending}>
              Create token
            </Button>
          </form>
          {tokenMutation.data ? (
            <p>
              Link:{" "}
              <a href={tokenMutation.data.link} target="_blank" rel="noreferrer">
                {tokenMutation.data.link}
              </a>
            </p>
          ) : null}
        </Card>
      </div>

      <Card title="Tokens">
        <p>Total: {tokensQ.data?.total || 0}</p>
        <table className="table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Used</th>
              <th>Expires</th>
            </tr>
          </thead>
          <tbody>
            {(tokensQ.data?.tokens || []).slice(0, 10).map((t) => (
              <tr key={t.token}>
                <td>{t.email}</td>
                <td><Badge tone={t.used ? "warn" : "ok"}>{t.used ? "Used" : "Ready"}</Badge></td>
                <td>{t.expires_at || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Check-ins">
        <p>Total: {checkinsQ.data?.total || 0}</p>
        <table className="table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Checked in at</th>
            </tr>
          </thead>
          <tbody>
            {(checkinsQ.data?.checkins || []).slice(0, 10).map((c) => (
              <tr key={`${c.email}-${c.checked_in_at}`}>
                <td>{c.email}</td>
                <td>{c.checked_in_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Responses">
        <p>Interested: {responsesQ.data?.total_interested || 0} | Unsubscribed: {responsesQ.data?.total_unsubscribed || 0}</p>
      </Card>
    </div>
  );
}

