import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Button, Card, EmptyState, PageHeader, StatCard } from "../components/ui";
import { DonutChartCard, SimpleBarChartCard } from "../components/charts";

export default function ViewsPage() {
  const [status, setStatus] = useState("");
  const placesQ = useQuery({ queryKey: ["places", status], queryFn: () => api.getPlaces(status || undefined) });
  const statsQ = useQuery({ queryKey: ["stats"], queryFn: api.getStats });

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
  const typeData = useMemo(
    () =>
      Object.entries(statsQ.data?.discovered_types || {}).map(([name, value]) => ({
        name,
        value,
      })),
    [statsQ.data],
  );

  return (
    <div className="page-stack">
      <PageHeader title="Views" subtitle="ภาพรวมข้อมูล scrape และผลประมวลผล" />
      <div className="kpi-grid">
        <StatCard label="Places" value={statsQ.data?.total_places ?? 0} />
        <StatCard label="Emails" value={statsQ.data?.total_emails ?? 0} />
        <StatCard label="Discovered URLs" value={statsQ.data?.total_discovered ?? 0} />
        <StatCard label="Success Rate" value={successRate} />
      </div>
      <div className="split-grid">
        <Card title="Place Status (click to filter table)" actions={status ? <Button variant="ghost" onClick={() => setStatus("")}>Clear</Button> : null}>
          <DonutChartCard data={statusData} onSelect={setStatus} selectedName={status} />
        </Card>
        <Card title="Discovered URL Types">
          <SimpleBarChartCard data={typeData} />
        </Card>
      </div>
      <Card title="Places">
        <div className="toolbar">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="NEW">NEW</option>
            <option value="DONE">DONE</option>
            <option value="FAILED">FAILED</option>
          </select>
        </div>
        {placesQ.isPending ? (
          <EmptyState title="Loading places..." message="กำลังดึงข้อมูลจาก API" />
        ) : placesQ.isError ? (
          <EmptyState title="โหลดข้อมูลไม่สำเร็จ" message={(placesQ.error as Error)?.message || "Unknown error"} />
        ) : !placesQ.data?.data?.length ? (
          <EmptyState title="ยังไม่มีข้อมูล" message="รัน Pipeline จากหน้า Dashboard แล้วกลับมาดูอีกครั้ง" />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Place</th>
                <th>Category</th>
                <th>Status</th>
                <th>Phone</th>
                <th>Website</th>
              </tr>
            </thead>
            <tbody>
              {placesQ.data.data.map((p) => (
                <tr key={p.place_id}>
                  <td>{p.name}</td>
                  <td>{p.category || "-"}</td>
                  <td>{p.status || "-"}</td>
                  <td>{p.phone || "-"}</td>
                  <td>{p.website || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

