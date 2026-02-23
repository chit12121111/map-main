import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../lib/api";
import { Badge, Button, Card, EmptyState, PageHeader, StatCard } from "../components/ui";
import { DonutChartCard, SimpleBarChartCard } from "../components/charts";
import thLocationsRaw from "../../../data/th_locations.json?raw";

type ThailandLocationMap = Record<string, Record<string, string[]>>;

export default function DashboardPage() {
  const DEFAULT_CONCURRENCY = 2;
  const DEFAULT_INACTIVITY = "3m";
  const DEFAULT_RADIUS = 7000;
  const DEFAULT_DEPTH = 2;
  const [query, setQuery] = useState("");
  const [district, setDistrict] = useState("");
  const [province, setProvince] = useState("");
  const [lastRunQuery, setLastRunQuery] = useState("");
  const [lang, setLang] = useState("th");
  const [depth, setDepth] = useState(DEFAULT_DEPTH);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");

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

  const provinceOptions = provinces;

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

  useEffect(() => {
    if (province && !provinceOptions.includes(province)) {
      setProvince("");
    }
  }, [province, provinceOptions]);

  useEffect(() => {
    if (district && !districtOptions.includes(district)) {
      setDistrict("");
    }
  }, [district, districtOptions]);

  const statsQ = useQuery({ queryKey: ["stats"], queryFn: api.getStats });
  const healthQ = useQuery({ queryKey: ["health-dashboard"], queryFn: api.health, retry: 0 });
  const placesQ = useQuery({ queryKey: ["dashboard-places"], queryFn: () => api.getPlaces() });
  const emailsQ = useQuery({ queryKey: ["dashboard-emails"], queryFn: () => api.getEmails({ includePlace: true }) });
  const runMutation = useMutation({
    mutationFn: api.runPipeline,
  });

  const successRate = useMemo(() => {
    const stats = statsQ.data;
    if (!stats || !stats.total_places) return "0.0%";
    const done = stats.status_breakdown?.DONE || 0;
    return `${((done / stats.total_places) * 100).toFixed(1)}%`;
  }, [statsQ.data]);

  const onRun = (e: FormEvent) => {
    e.preventDefault();
    const finalQuery = [query.trim(), district.trim(), province.trim()].filter(Boolean).join(" ");
    if (!finalQuery) return;
    setLastRunQuery(finalQuery);
    runMutation.mutate({
      query: finalQuery,
      concurrency: DEFAULT_CONCURRENCY,
      lang,
      inactivity: DEFAULT_INACTIVITY,
      radius: DEFAULT_RADIUS,
      depth,
    });
  };

  const statusData = useMemo(
    () =>
      Object.entries(statsQ.data?.status_breakdown || {}).map(([name, value]) => ({
        name,
        value,
      })),
    [statsQ.data],
  );
  const sourceData = useMemo(
    () =>
      Object.entries(statsQ.data?.source_breakdown || {}).map(([name, value]) => ({
        name,
        value,
      })),
    [statsQ.data],
  );
  const filteredPlaces = useMemo(
    () => (placesQ.data?.data || []).filter((p) => (statusFilter ? (p.status || "UNKNOWN") === statusFilter : true)).slice(0, 8),
    [placesQ.data, statusFilter],
  );
  const filteredEmails = useMemo(
    () => (emailsQ.data?.data || []).filter((e) => (sourceFilter ? e.source === sourceFilter : true)).slice(0, 8),
    [emailsQ.data, sourceFilter],
  );

  return (
    <div className="page-stack">
      <PageHeader
        title="Dashboard"
        subtitle="KPI + Analytics + Runner + Health"
        right={
          <div className="row gap-sm">
            <Badge tone={healthQ.isSuccess ? "ok" : "warn"}>{healthQ.isSuccess ? "API Ready" : "API Offline"}</Badge>
            <Badge tone="info">Fast + Geo Runner</Badge>
          </div>
        }
      />

      <div className="kpi-grid">
        <StatCard label="Places" value={statsQ.data?.total_places ?? 0} />
        <StatCard label="Emails" value={statsQ.data?.total_emails ?? 0} />
        <StatCard label="Discovered URLs" value={statsQ.data?.total_discovered ?? 0} />
        <StatCard label="Success Rate" value={successRate} trend="DONE / ALL" />
      </div>

      <div className="split-grid">
        <Card title="Status Breakdown" actions={statusFilter ? <Button variant="ghost" onClick={() => setStatusFilter("")}>Clear</Button> : null}>
          <DonutChartCard data={statusData} onSelect={setStatusFilter} selectedName={statusFilter} />
        </Card>
        <Card title="Email Sources" actions={sourceFilter ? <Button variant="ghost" onClick={() => setSourceFilter("")}>Clear</Button> : null}>
          <SimpleBarChartCard data={sourceData} onSelect={setSourceFilter} selectedName={sourceFilter} />
        </Card>
      </div>

      <div className="split-grid">
        <Card title={`Places ${statusFilter ? `(${statusFilter})` : "(All)"}`}>
          {placesQ.isPending ? (
            <EmptyState title="Loading places..." message="กำลังดึงข้อมูลจาก API" />
          ) : placesQ.isError ? (
            <EmptyState title="โหลดข้อมูล places ไม่สำเร็จ" message={(placesQ.error as Error)?.message || "Unknown error"} />
          ) : !filteredPlaces.length ? (
            <EmptyState title="ไม่มีรายการตาม filter" message="คลิก segment อื่นจากกราฟ หรือ clear filter" />
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Category</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredPlaces.map((p) => (
                  <tr key={p.place_id}>
                    <td>{p.name}</td>
                    <td>{p.category || "-"}</td>
                    <td>{p.status || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card title={`Emails ${sourceFilter ? `(${sourceFilter})` : "(All)"}`}>
          {emailsQ.isPending ? (
            <EmptyState title="Loading emails..." message="กำลังดึงข้อมูลจาก API" />
          ) : emailsQ.isError ? (
            <EmptyState title="โหลดข้อมูล emails ไม่สำเร็จ" message={(emailsQ.error as Error)?.message || "Unknown error"} />
          ) : !filteredEmails.length ? (
            <EmptyState title="ไม่มีรายการตาม filter" message="คลิกแท่งอื่นจากกราฟ หรือ clear filter" />
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {filteredEmails.map((e) => (
                  <tr key={e.id}>
                    <td>{e.email}</td>
                    <td>{e.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      <div className="split-grid">
        <Card title="Health & Activity" compact>
          <div className="kv-list">
            <div><span>Last Query</span><strong>{lastRunQuery || "(ยังไม่มี)"}</strong></div>
            <div><span>API Status</span><strong>{healthQ.isSuccess ? "Ready" : healthQ.isPending ? "Checking" : "Offline"}</strong></div>
            <div><span>Runner Mode</span><strong>Sequential Stage 1-4</strong></div>
          </div>
        </Card>
        <Card title="Runner Health" compact>
          {!healthQ.isSuccess ? (
            <EmptyState title="ยังดึงข้อมูลจาก API ไม่ได้" message="ตรวจว่า Laravel API เปิดอยู่และตั้ง VITE_API_BASE_URL ถูกต้อง" />
          ) : (
            <div className="column gap-sm">
              <Badge tone="ok">API Connected</Badge>
              <Badge tone="ok">Dashboard Ready</Badge>
            </div>
          )}
        </Card>
      </div>

      <Card title="Pipeline Runner" actions={<Badge tone="warn">Primary Workflow</Badge>}>
        <p className="runner-note">
          เลือกพื้นที่ให้ชัดเจนเพื่อผลลัพธ์ที่แม่นขึ้น จากนั้นกดเริ่มรัน Pipeline ได้ทันที
        </p>
        <form className="runner-form" onSubmit={onRun}>
          <label className="runner-field runner-field-wide">
            Keyword
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="เช่น โรงแรม, ร้านกาแฟ, คลินิก" />
          </label>
          <label className="runner-field">
            จังหวัด
            <input
              value={province}
              onChange={(e) => setProvince(e.target.value)}
              list="province-options"
              placeholder="เลือกจังหวัด"
            />
            <datalist id="province-options">
              {provinceOptions.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </label>
          <label className="runner-field">
            อำเภอ / เขต
            <input
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
              list="district-options"
              placeholder="เลือกอำเภอ / เขต"
            />
            <datalist id="district-options">
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
              max={10}
              step={1}
              value={depth}
              onChange={(e) => setDepth(Math.max(1, Math.min(10, Number(e.target.value) || DEFAULT_DEPTH)))}
            />
          </label>
          <div className="runner-actions">
            <Button
              variant="primary"
              type="submit"
              disabled={runMutation.isPending || ![query.trim(), district.trim(), province.trim()].some(Boolean)}
            >
              {runMutation.isPending ? "Running..." : "Start Pipeline"}
            </Button>
          </div>
        </form>

        {runMutation.isError ? <p className="text-error">Run failed: {(runMutation.error as Error).message}</p> : null}
        {runMutation.data ? (
          <div className="runner-output">
            <p>
              Result: {runMutation.data.ok ? "Success" : "Failed"} | Rows: {runMutation.data.rows ?? 0} | Time:{" "}
              {runMutation.data.elapsed_ms ? `${Math.round(runMutation.data.elapsed_ms / 1000)}s` : "-"}
            </p>
            <pre>{(runMutation.data.output || []).join("\n")}</pre>
          </div>
        ) : null}
      </Card>
    </div>
  );
}

