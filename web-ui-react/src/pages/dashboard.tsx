import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api } from "../lib/api";
import { Badge, Button, Card, EmptyState, PageHeader, StatCard } from "../components/ui";
import { DonutChartCard, SimpleBarChartCard } from "../components/charts";

export default function DashboardPage() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");

  const statsQ = useQuery({ queryKey: ["stats"], queryFn: api.getStats });
  const healthQ = useQuery({ queryKey: ["health-dashboard"], queryFn: api.health, retry: 0 });
  const placesQ = useQuery({ queryKey: ["dashboard-places"], queryFn: () => api.getPlaces() });
  const emailsQ = useQuery({ queryKey: ["dashboard-emails"], queryFn: () => api.getEmails({ includePlace: true }) });

  const successRate = useMemo(() => {
    const stats = statsQ.data;
    if (!stats || !stats.total_places) return "0.0%";
    const done = stats.status_breakdown?.DONE || 0;
    return `${((done / stats.total_places) * 100).toFixed(1)}%`;
  }, [statsQ.data]);

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
  const allPlaces = useMemo(() => (placesQ.data?.data || []).slice(0, 8), [placesQ.data]);
  const allEmails = useMemo(() => (emailsQ.data?.data || []).slice(0, 8), [emailsQ.data]);
  const placesRows = filteredPlaces.length ? filteredPlaces : allPlaces;
  const emailsRows = filteredEmails.length ? filteredEmails : allEmails;
  const placesFallbackToAll = Boolean(statusFilter) && !filteredPlaces.length && allPlaces.length > 0;
  const emailsFallbackToAll = Boolean(sourceFilter) && !filteredEmails.length && allEmails.length > 0;

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
          <DonutChartCard
            data={statusData}
            onSelect={setStatusFilter}
            selectedName={statusFilter}
            showAllButton
            repeatSelectFallbackName="NEW"
          />
        </Card>
        <Card title="Email Sources" actions={sourceFilter ? <Button variant="ghost" onClick={() => setSourceFilter("")}>Clear</Button> : null}>
          <SimpleBarChartCard data={sourceData} onSelect={setSourceFilter} selectedName={sourceFilter} />
        </Card>
      </div>

      <div className="split-grid">
        <Card title={`Places ${placesFallbackToAll ? "(All)" : statusFilter ? `(${statusFilter})` : "(All)"}`}>
          {placesQ.isPending ? (
            <EmptyState title="Loading places..." message="กำลังดึงข้อมูลจาก API" />
          ) : placesQ.isError ? (
            <EmptyState title="โหลดข้อมูล places ไม่สำเร็จ" message={(placesQ.error as Error)?.message || "Unknown error"} />
          ) : !placesRows.length ? (
            <EmptyState title="ยังไม่มีข้อมูล" message="รัน Pipeline จากหน้า Logs แล้วกลับมาดูอีกครั้ง" />
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
                {placesRows.map((p) => (
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
        <Card title={`Emails ${emailsFallbackToAll ? "(All)" : sourceFilter ? `(${sourceFilter})` : "(All)"}`}>
          {emailsQ.isPending ? (
            <EmptyState title="Loading emails..." message="กำลังดึงข้อมูลจาก API" />
          ) : emailsQ.isError ? (
            <EmptyState title="โหลดข้อมูล emails ไม่สำเร็จ" message={(emailsQ.error as Error)?.message || "Unknown error"} />
          ) : !emailsRows.length ? (
            <EmptyState title="ยังไม่มีข้อมูล" message="รอ Stage 2-4 ประมวลผลเพิ่มเติม" />
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {emailsRows.map((e) => (
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

    </div>
  );
}

