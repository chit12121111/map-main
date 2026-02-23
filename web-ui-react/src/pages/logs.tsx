import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Button, Card, EmptyState, Input, PageHeader } from "../components/ui";
import thLocationsRaw from "../../../data/th_locations.json?raw";

type ThailandLocationMap = Record<string, Record<string, string[]>>;

function formatElapsed(ms?: number | null): string {
  if (!ms || ms <= 0) return "00:00";
  const totalSeconds = Math.floor(ms / 1000);
  const mm = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const ss = String(totalSeconds % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export default function LogsPage() {
  const DEFAULT_CONCURRENCY = 2;
  const DEFAULT_INACTIVITY = "3m";
  const DEFAULT_RADIUS = 7000;
  const DEFAULT_DEPTH = 2;
  const MAX_DEPTH = 100;

  const [query, setQuery] = useState("");
  const [district, setDistrict] = useState("");
  const [province, setProvince] = useState("");
  const [lang, setLang] = useState("th");
  const [depthInput, setDepthInput] = useState(String(DEFAULT_DEPTH));
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [logSearch, setLogSearch] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [paused, setPaused] = useState(false);
  const [liveElapsedMs, setLiveElapsedMs] = useState<number>(0);
  const logsRef = useRef<HTMLPreElement | null>(null);
  const prefHydratedRef = useRef(false);

  const locationMap = useMemo<ThailandLocationMap>(() => {
    try {
      return JSON.parse(thLocationsRaw) as ThailandLocationMap;
    } catch {
      return {};
    }
  }, []);

  const provinces = useMemo(() => {
    const all = new Set<string>();
    Object.values(locationMap).forEach((regionMap) => {
      Object.keys(regionMap).forEach((provinceName) => all.add(provinceName));
    });
    return Array.from(all).sort((a, b) => a.localeCompare(b, "th"));
  }, [locationMap]);

  const districtOptions = useMemo(() => {
    const all = new Set<string>();
    Object.values(locationMap).forEach((regionMap) => {
      Object.entries(regionMap).forEach(([provinceName, districts]) => {
        if (!province || provinceName === province) {
          districts.forEach((districtName) => all.add(districtName));
        }
      });
    });
    return Array.from(all).sort((a, b) => a.localeCompare(b, "th"));
  }, [locationMap, province]);

  const prefQ = useQuery({
    queryKey: ["ui-pref", "logs-ui"],
    queryFn: () => api.getUiPreference("logs-ui"),
    staleTime: 60_000,
  });

  const statusQ = useQuery({
    queryKey: ["pipeline-status"],
    queryFn: api.getPipelineStatus,
    refetchInterval: paused ? false : (q) => (q.state.data?.running ? 1000 : 4000),
  });

  const runsQ = useQuery({
    queryKey: ["pipeline-runs"],
    queryFn: () => api.getPipelineRuns(60),
    refetchInterval: paused ? false : (statusQ.data?.running ? 2500 : 8000),
  });

  const runDetailQ = useQuery({
    queryKey: ["pipeline-run", selectedRunId],
    queryFn: () => api.getPipelineRun(Number(selectedRunId)),
    enabled: selectedRunId !== null,
    refetchInterval: paused ? false : (statusQ.data?.running ? 1500 : 8000),
  });

  const runLogsQ = useQuery({
    queryKey: ["pipeline-run-logs", selectedRunId],
    queryFn: () => api.getPipelineRunLogs(Number(selectedRunId), { limit: 1000 }),
    enabled: selectedRunId !== null,
    refetchInterval: paused ? false : (statusQ.data?.running ? 1000 : 5000),
  });

  const runMutation = useMutation({
    mutationFn: api.runPipeline,
    onSuccess: (res) => {
      if (res.run_id) setSelectedRunId(res.run_id);
    },
  });

  const savePrefMutation = useMutation({
    mutationFn: (value: Record<string, unknown>) => api.putUiPreference("logs-ui", value),
  });

  const depth = useMemo(() => {
    const n = Number(depthInput);
    if (!Number.isFinite(n)) return DEFAULT_DEPTH;
    return Math.max(1, Math.min(MAX_DEPTH, Math.trunc(n)));
  }, [depthInput]);

  useEffect(() => {
    if (prefHydratedRef.current) return;
    const pref = prefQ.data?.value;
    if (!pref || typeof pref !== "object") return;
    const v = pref as Record<string, unknown>;
    if (typeof v.query === "string") setQuery(v.query);
    if (typeof v.province === "string") setProvince(v.province);
    if (typeof v.district === "string") setDistrict(v.district);
    if (typeof v.lang === "string") setLang(v.lang);
    if (typeof v.depth === "number") setDepthInput(String(v.depth));
    if (typeof v.selectedRunId === "number") setSelectedRunId(v.selectedRunId);
    if (typeof v.logSearch === "string") setLogSearch(v.logSearch);
    if (typeof v.autoScroll === "boolean") setAutoScroll(v.autoScroll);
    if (typeof v.paused === "boolean") setPaused(v.paused);
    prefHydratedRef.current = true;
  }, [prefQ.data]);

  useEffect(() => {
    if (!prefHydratedRef.current) return;
    const timer = setTimeout(() => {
      savePrefMutation.mutate({
        query,
        province,
        district,
        lang,
        depth,
        selectedRunId,
        logSearch,
        autoScroll,
        paused,
      });
    }, 300);
    return () => clearTimeout(timer);
  }, [query, province, district, lang, depth, selectedRunId, logSearch, autoScroll, paused]);

  useEffect(() => {
    if (selectedRunId !== null) return;
    const preferred = statusQ.data?.run_id;
    if (preferred) {
      setSelectedRunId(preferred);
      return;
    }
    const latest = runsQ.data?.runs?.[0];
    if (latest) setSelectedRunId(latest.id);
  }, [selectedRunId, statusQ.data, runsQ.data]);

  useEffect(() => {
    if (!statusQ.data?.running || !statusQ.data?.started_at) {
      setLiveElapsedMs(statusQ.data?.elapsed_ms ?? 0);
      return;
    }
    const startedAt = new Date(statusQ.data.started_at).getTime();
    const update = () => setLiveElapsedMs(Math.max(0, Date.now() - startedAt));
    update();
    const intId = setInterval(update, 1000);
    return () => clearInterval(intId);
  }, [statusQ.data?.running, statusQ.data?.started_at, statusQ.data?.elapsed_ms]);

  const liveStatus = runDetailQ.data || runsQ.data?.runs?.find((r) => r.id === selectedRunId) || null;
  const logs = runLogsQ.data?.logs || [];

  const filteredLogs = useMemo(() => {
    if (!logSearch.trim()) return logs;
    const keyword = logSearch.toLowerCase();
    return logs.filter((l) => l.line.toLowerCase().includes(keyword));
  }, [logs, logSearch]);

  useEffect(() => {
    if (!autoScroll) return;
    if (!logsRef.current) return;
    logsRef.current.scrollTop = logsRef.current.scrollHeight;
  }, [filteredLogs, autoScroll]);

  const statusTone = statusQ.data?.running
    ? "warn"
    : liveStatus?.status === "SUCCESS"
      ? "ok"
      : liveStatus?.status === "FAILED"
        ? "bad"
        : "neutral";

  const statusLabel = statusQ.data?.running
    ? "RUNNING"
    : liveStatus?.status === "SUCCESS"
      ? "SUCCESS"
      : liveStatus?.status === "FAILED"
        ? "FAILED"
        : "IDLE";

  const onRun = (e: FormEvent) => {
    e.preventDefault();
    const finalQuery = [query.trim(), district.trim(), province.trim()].filter(Boolean).join(" ");
    if (!finalQuery) return;
    runMutation.mutate({
      query: finalQuery,
      concurrency: DEFAULT_CONCURRENCY,
      lang,
      inactivity: DEFAULT_INACTIVITY,
      radius: DEFAULT_RADIUS,
      depth,
    });
  };

  return (
    <div className="page-stack">
      <PageHeader title="Pipeline Console" subtitle="Run pipeline, monitor live status, and review run history from one place" />

      <Card className="status-hero-card">
        <div className="status-hero-top">
          <Badge tone={statusTone}>{statusLabel}</Badge>
          <div className="status-hero-timer">{formatElapsed(statusQ.data?.running ? liveElapsedMs : (liveStatus?.elapsed_ms ?? 0))}</div>
          <div className="row gap-sm">
            <Button variant="ghost" onClick={() => setPaused((v) => !v)}>{paused ? "Resume live" : "Pause live"}</Button>
            <Button variant="secondary" onClick={() => { void statusQ.refetch(); void runsQ.refetch(); if (selectedRunId) { void runDetailQ.refetch(); void runLogsQ.refetch(); } }}>Refresh</Button>
          </div>
        </div>
        <div className="status-hero-meta">
          <span>Run ID: <strong>{liveStatus?.id ?? statusQ.data?.run_id ?? "-"}</strong></span>
          <span>Rows: <strong>{liveStatus?.rows ?? statusQ.data?.rows ?? "-"}</strong></span>
          <span>Started: <strong>{liveStatus?.started_at ?? statusQ.data?.started_at ?? "-"}</strong></span>
          <span>Finished: <strong>{liveStatus?.finished_at ?? statusQ.data?.finished_at ?? "-"}</strong></span>
        </div>
      </Card>

      <div className="split-grid">
        <Card title="System Status">
          {statusQ.isPending ? (
            <EmptyState title="Loading status..." message="กำลังอ่านสถานะ pipeline ล่าสุด" />
          ) : statusQ.isError ? (
            <EmptyState title="โหลดสถานะไม่สำเร็จ" message={(statusQ.error as Error)?.message || "Unknown error"} />
          ) : (
            <div className="kv-list">
              <div><span>Running</span><strong>{statusQ.data?.running ? "Yes" : "No"}</strong></div>
              <div><span>Status</span><strong>{statusQ.data?.status || liveStatus?.status || "-"}</strong></div>
              <div><span>Last Query</span><strong>{statusQ.data?.last_query || liveStatus?.query || "-"}</strong></div>
              <div><span>Error</span><strong>{statusQ.data?.error || liveStatus?.error || "-"}</strong></div>
            </div>
          )}
        </Card>

        <Card title="Run History">
          {!runsQ.data?.runs?.length ? (
            <EmptyState title="No run history" message="ยังไม่มีประวัติการรันในระบบ" />
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Status</th>
                  <th>Rows</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {runsQ.data.runs.map((r) => (
                  <tr key={r.id}>
                    <td>#{r.id}</td>
                    <td><Badge tone={r.status === "SUCCESS" ? "ok" : r.status === "FAILED" ? "bad" : r.status === "RUNNING" ? "warn" : "neutral"}>{r.status}</Badge></td>
                    <td>{r.rows ?? "-"}</td>
                    <td><Button variant="secondary" onClick={() => setSelectedRunId(r.id)}>Open</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      <Card title="Pipeline Runner">
        <p className="runner-note">เลือกพื้นที่ให้ชัดเจนแล้วกดเริ่มรัน จากนั้นติดตามผลแบบ live ได้ด้านล่างทันที</p>
        <form className="runner-form" onSubmit={onRun}>
          <label className="runner-field runner-field-wide">
            Keyword
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="เช่น โรงแรม, ร้านกาแฟ, คลินิก" />
          </label>
          <label className="runner-field">
            จังหวัด
            <input
              type="text"
              autoComplete="off"
              value={province}
              onChange={(e) => setProvince(e.target.value)}
              list="province-options-logs"
              placeholder="พิมพ์หรือเลือกจังหวัด"
            />
            <datalist id="province-options-logs">
              {provinces.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </label>
          <label className="runner-field">
            อำเภอ / เขต
            <input
              type="text"
              autoComplete="off"
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
              list="district-options-logs"
              placeholder="พิมพ์หรือเลือกอำเภอ / เขต"
            />
            <datalist id="district-options-logs">
              {districtOptions.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </label>
          <label className="runner-field">
            Language
            <select value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="th">ไทย</option>
              <option value="en">English</option>
            </select>
          </label>
          <label className="runner-field">
            Depth
            <input
              type="number"
              min={1}
              max={MAX_DEPTH}
              step={1}
              value={depthInput}
              onChange={(e) => setDepthInput(e.target.value)}
              onBlur={() => setDepthInput(String(depth))}
            />
          </label>
          <div className="runner-actions">
            <Button variant="primary" type="submit" disabled={runMutation.isPending || ![query.trim(), district.trim(), province.trim()].some(Boolean)}>
              {runMutation.isPending ? "Running..." : "Start Pipeline"}
            </Button>
          </div>
        </form>
        {runMutation.isError ? <p className="text-error">Run failed: {(runMutation.error as Error).message}</p> : null}
      </Card>

      <Card title={`Run Logs ${selectedRunId ? `#${selectedRunId}` : ""}`} actions={
        <div className="row gap-sm">
          <Input placeholder="Search logs..." value={logSearch} onChange={(e) => setLogSearch(e.target.value)} />
          <Button variant="ghost" onClick={() => setAutoScroll((v) => !v)}>{autoScroll ? "Auto-scroll: ON" : "Auto-scroll: OFF"}</Button>
          <Button
            variant="secondary"
            onClick={() => navigator.clipboard.writeText(filteredLogs.map((l) => l.line).join("\n"))}
            disabled={!filteredLogs.length}
          >
            Copy
          </Button>
        </div>
      }>
        {!selectedRunId ? (
          <EmptyState title="ยังไม่ได้เลือก run" message="เลือกรายการจาก Run History เพื่อดู log" />
        ) : runLogsQ.isPending ? (
          <EmptyState title="Loading logs..." message="กำลังดึง run logs ล่าสุด" />
        ) : runLogsQ.isError ? (
          <EmptyState title="โหลด logs ไม่สำเร็จ" message={(runLogsQ.error as Error)?.message || "Unknown error"} />
        ) : !filteredLogs.length ? (
          <EmptyState title="No logs found" message={logSearch ? "ไม่พบ log ตามคำค้น" : "ยังไม่มี log สำหรับ run นี้"} />
        ) : (
          <div className="runner-output">
            <pre ref={logsRef}>
              {filteredLogs.map((line) => `[${String(line.seq).padStart(4, "0")}] ${line.line}`).join("\n")}
            </pre>
          </div>
        )}
      </Card>
    </div>
  );
}
