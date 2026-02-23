import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { API_BASE_URL, api } from "../lib/api";
import { Badge, Button, Card, EmptyState, Input, PageHeader } from "../components/ui";

export default function SettingsPage() {
  const [confirmClear, setConfirmClear] = useState("");
  const [cfgApiBase, setCfgApiBase] = useState(API_BASE_URL);
  const [cfgInternalApiUrl, setCfgInternalApiUrl] = useState("http://127.0.0.1:8010");
  const [cfgGoogleClientId, setCfgGoogleClientId] = useState((import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined) || "");
  const [campaignSubject, setCampaignSubject] = useState("Hello from Mapping Pipeline");
  const [campaignBody, setCampaignBody] = useState("Hi, we are reaching out from Mapping Pipeline.");
  const [campaignStatus, setCampaignStatus] = useState("DONE");
  const [campaignProvince, setCampaignProvince] = useState("");
  const [campaignSource, setCampaignSource] = useState("");
  const [campaignLimit, setCampaignLimit] = useState(200);
  const [selectedCampaignId, setSelectedCampaignId] = useState<number | null>(null);
  const [previewRecipients, setPreviewRecipients] = useState<Array<{ email: string; place_id: string; source: string }>>([]);
  const [selectedRecipients, setSelectedRecipients] = useState<Record<string, boolean>>({});

  const configQ = useQuery({ queryKey: ["ui-pref", "settings-config"], queryFn: () => api.getUiPreference("settings-config") });
  const campaignsQ = useQuery({ queryKey: ["email-campaigns"], queryFn: () => api.getEmailCampaigns(20), refetchInterval: 5000 });
  const campaignDetailQ = useQuery({
    queryKey: ["email-campaign", selectedCampaignId],
    queryFn: () => api.getEmailCampaign(Number(selectedCampaignId)),
    enabled: selectedCampaignId !== null,
    refetchInterval: 3000,
  });
  const clearMutation = useMutation({ mutationFn: api.clearAll });
  const saveConfigMutation = useMutation({
    mutationFn: (value: Record<string, unknown>) => api.putUiPreference("settings-config", value),
    onSuccess: () => {
      void configQ.refetch();
    },
  });
  const previewCampaignMutation = useMutation({
    mutationFn: () =>
      api.previewEmailCampaign({
        status: campaignStatus || undefined,
        province: campaignProvince || undefined,
        source: campaignSource || undefined,
        limit: campaignLimit,
      }),
    onSuccess: (res) => {
      setPreviewRecipients(res.recipients || []);
      const picked: Record<string, boolean> = {};
      (res.recipients || []).forEach((r) => {
        picked[r.email] = true;
      });
      setSelectedRecipients(picked);
    },
  });
  const sendCampaignMutation = useMutation({
    mutationFn: () =>
      api.sendEmailCampaign({
        subject: campaignSubject,
        body_text: campaignBody,
        status: campaignStatus || undefined,
        province: campaignProvince || undefined,
        source: campaignSource || undefined,
        limit: campaignLimit,
        selected_emails: Object.keys(selectedRecipients).filter((email) => selectedRecipients[email]),
      }),
    onSuccess: (res) => {
      void campaignsQ.refetch();
      if (res.campaign_id) setSelectedCampaignId(res.campaign_id);
    },
  });

  useEffect(() => {
    const value = configQ.data?.value;
    if (!value || typeof value !== "object") return;
    if (typeof value.apiBaseUrl === "string") setCfgApiBase(value.apiBaseUrl);
    if (typeof value.internalApiUrl === "string") setCfgInternalApiUrl(value.internalApiUrl);
    if (typeof value.googleClientId === "string") setCfgGoogleClientId(value.googleClientId);
  }, [configQ.data]);

  const onSaveConfig = (ev: FormEvent) => {
    ev.preventDefault();
    saveConfigMutation.mutate({
      apiBaseUrl: cfgApiBase.trim(),
      internalApiUrl: cfgInternalApiUrl.trim(),
      googleClientId: cfgGoogleClientId.trim(),
    });
  };

  const googleOAuthUrl = (() => {
    const direct = (import.meta.env.VITE_GOOGLE_OAUTH_URL as string | undefined)?.trim();
    if (direct) return direct;
    const clientId = cfgGoogleClientId.trim() || (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined)?.trim();
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
        <Card title="System Config">
          {configQ.isPending ? (
            <EmptyState title="Loading config..." message="กำลังอ่านค่าตั้งค่าที่บันทึกไว้" />
          ) : (
            <form className="runner-form" onSubmit={onSaveConfig}>
              <label className="runner-field runner-field-wide">
                API Base URL
                <Input value={cfgApiBase} onChange={(e) => setCfgApiBase(e.target.value)} placeholder="http://127.0.0.1:8000" />
              </label>
              <label className="runner-field">
                Internal API URL
                <Input value={cfgInternalApiUrl} onChange={(e) => setCfgInternalApiUrl(e.target.value)} placeholder="http://127.0.0.1:8010" />
              </label>
              <label className="runner-field runner-field-wide">
                GOOGLE_CLIENT_ID
                <Input
                  value={cfgGoogleClientId}
                  onChange={(e) => setCfgGoogleClientId(e.target.value)}
                  placeholder="your_client_id.apps.googleusercontent.com"
                />
              </label>
              <div className="runner-actions">
                <Button variant="primary" type="submit" disabled={saveConfigMutation.isPending}>
                  {saveConfigMutation.isPending ? "Saving..." : "Save Config"}
                </Button>
              </div>
            </form>
          )}
          {saveConfigMutation.isError ? <p className="text-error">{(saveConfigMutation.error as Error).message}</p> : null}
          {saveConfigMutation.isSuccess ? <p>Configuration saved.</p> : null}
        </Card>

        <Card title="Login Integrations">
          <div className="column gap-sm">
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
          <p>Type <strong>CLEAR</strong> to confirm destructive action.</p>
          <Input value={confirmClear} onChange={(e) => setConfirmClear(e.target.value)} placeholder="Type CLEAR to enable" />
          <div className="row gap-sm">
            <Button variant="danger" onClick={() => clearMutation.mutate()} disabled={clearMutation.isPending || confirmClear.trim().toUpperCase() !== "CLEAR"}>
              {clearMutation.isPending ? "Clearing..." : "Clear places/emails/urls"}
            </Button>
          </div>
          {clearMutation.data ? <p>{clearMutation.data.message}</p> : null}
          {clearMutation.isError ? <p className="text-error">{(clearMutation.error as Error).message}</p> : null}
        </Card>

      </div>

      <Card title="Email Automation">
        <form className="runner-form" onSubmit={(e) => { e.preventDefault(); sendCampaignMutation.mutate(); }}>
          <label className="runner-field runner-field-wide">
            Subject
            <Input value={campaignSubject} onChange={(e) => setCampaignSubject(e.target.value)} placeholder="Email subject" />
          </label>
          <label className="runner-field runner-field-wide">
            Body
            <textarea
              value={campaignBody}
              onChange={(e) => setCampaignBody(e.target.value)}
              placeholder="Email body"
              rows={5}
              style={{ border: "1px solid #cbd5e1", borderRadius: 10, padding: 12, fontSize: 14 }}
            />
          </label>
          <label className="runner-field">
            Filter Status
            <select value={campaignStatus} onChange={(e) => setCampaignStatus(e.target.value)}>
              <option value="">All</option>
              <option value="NEW">NEW</option>
              <option value="DONE">DONE</option>
              <option value="FAILED">FAILED</option>
            </select>
          </label>
          <label className="runner-field">
            Filter Province
            <Input value={campaignProvince} onChange={(e) => setCampaignProvince(e.target.value)} placeholder="optional" />
          </label>
          <label className="runner-field">
            Filter Source
            <Input value={campaignSource} onChange={(e) => setCampaignSource(e.target.value)} placeholder="MAPS / WEBSITE / ..." />
          </label>
          <label className="runner-field">
            Recipient Limit
            <Input type="number" min={1} max={10000} value={campaignLimit} onChange={(e) => setCampaignLimit(Math.max(1, Number(e.target.value) || 1))} />
          </label>
          <div className="runner-actions">
            <div className="row gap-sm">
              <Button variant="secondary" type="button" onClick={() => previewCampaignMutation.mutate()} disabled={previewCampaignMutation.isPending}>
                {previewCampaignMutation.isPending ? "Previewing..." : "Preview Recipients"}
              </Button>
              <Button variant="primary" type="submit" disabled={sendCampaignMutation.isPending || !campaignSubject.trim() || !campaignBody.trim()}>
                {sendCampaignMutation.isPending ? "Queueing..." : "Send Campaign"}
              </Button>
            </div>
          </div>
        </form>
        <p className="runner-note">
          Tip: use <code>{"{{checkin_link}}"}</code> in Body to auto-insert unique token link per recipient.
        </p>
        {previewCampaignMutation.data ? (
          <p>Preview recipients: <strong>{previewCampaignMutation.data.count}</strong> | Selected: <strong>{Object.keys(selectedRecipients).filter((email) => selectedRecipients[email]).length}</strong></p>
        ) : null}
        {previewCampaignMutation.isError ? <p className="text-error">{(previewCampaignMutation.error as Error).message}</p> : null}
        {previewRecipients.length ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th />
                  <th>Email</th>
                  <th>Place ID</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {previewRecipients.map((r) => (
                  <tr key={`${r.email}-${r.place_id}`}>
                    <td>
                      <input
                        type="checkbox"
                        checked={!!selectedRecipients[r.email]}
                        onChange={(e) => setSelectedRecipients((prev) => ({ ...prev, [r.email]: e.target.checked }))}
                      />
                    </td>
                    <td>{r.email}</td>
                    <td>{r.place_id}</td>
                    <td>{r.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {sendCampaignMutation.data ? (
          <p>Campaign queued. ID: <strong>{sendCampaignMutation.data.campaign_id ?? "-"}</strong> | Recipients: <strong>{sendCampaignMutation.data.count}</strong></p>
        ) : null}
        {sendCampaignMutation.isError ? <p className="text-error">{(sendCampaignMutation.error as Error).message}</p> : null}
      </Card>

      <Card title="Campaign Status">
        {campaignsQ.isPending ? (
          <EmptyState title="Loading campaigns..." message="กำลังดึงสถานะการส่งอีเมล" />
        ) : campaignsQ.isError ? (
          <EmptyState title="โหลด campaign ไม่สำเร็จ" message={(campaignsQ.error as Error)?.message || "Unknown error"} />
        ) : !(campaignsQ.data?.campaigns || []).length ? (
          <EmptyState title="No campaigns" message="ยังไม่มีการส่งอีเมลอัตโนมัติ" />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Recipients</th>
                <th>Sent</th>
                <th>Failed</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(campaignsQ.data?.campaigns || []).map((row) => (
                <tr key={row.id}>
                  <td>#{row.id}</td>
                  <td><Badge tone={row.status === "COMPLETED" ? "ok" : row.status === "SENDING" ? "warn" : "neutral"}>{row.status}</Badge></td>
                  <td>{row.total_recipients}</td>
                  <td>{row.sent_count}</td>
                  <td>{row.failed_count}</td>
                  <td><Button variant="secondary" onClick={() => setSelectedCampaignId(row.id)}>Open</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {selectedCampaignId && campaignDetailQ.data?.campaign ? (
          <div className="runner-note">
            Latest selected campaign #{campaignDetailQ.data.campaign.id}: pending {campaignDetailQ.data.campaign.pending_count}, sent {campaignDetailQ.data.campaign.sent_count}, failed {campaignDetailQ.data.campaign.failed_count}
            {" | "}
            response: interested {campaignDetailQ.data.response_summary?.INTERESTED ?? 0}, unsubscribed {campaignDetailQ.data.response_summary?.UNSUBSCRIBED ?? 0}, pending {campaignDetailQ.data.response_summary?.PENDING ?? 0}
          </div>
        ) : null}
      </Card>
    </div>
  );
}

