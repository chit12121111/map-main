import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Button, Card, EmptyState, Input, PageHeader, StatCard } from "../components/ui";

export default function CustomersPage() {
  const [q, setQ] = useState("");
  const nav = useNavigate();
  const emailsQ = useQuery({ queryKey: ["emails-with-place"], queryFn: () => api.getEmails({ includePlace: true }) });

  const rows = useMemo(() => {
    const list = emailsQ.data?.data || [];
    if (!q.trim()) return list;
    const keyword = q.toLowerCase();
    return list.filter((item) => {
      const name = item.place?.name?.toLowerCase() || "";
      const email = item.email.toLowerCase();
      return name.includes(keyword) || email.includes(keyword);
    });
  }, [emailsQ.data, q]);

  return (
    <div className="page-stack">
      <PageHeader title="Customers" subtitle="รายชื่อ customer จาก place + email ที่ติดต่อได้" right={<Badge tone="info">Contact Hub</Badge>} />
      <div className="kpi-grid">
        <StatCard label="Total rows" value={emailsQ.data?.total ?? 0} />
        <StatCard label="Filtered" value={rows.length} />
        <StatCard label="Email sources" value={new Set((emailsQ.data?.data || []).map((e) => e.source)).size} />
        <StatCard label="Ready to contact" value={rows.length} />
      </div>

      <Card title="Customer Table">
        <div className="toolbar">
          <Input placeholder="Search by name/email..." value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {emailsQ.isPending ? (
          <EmptyState title="Loading customers..." message="กำลังดึงข้อมูลจาก API" />
        ) : emailsQ.isError ? (
          <EmptyState title="โหลดข้อมูลลูกค้าไม่สำเร็จ" message={(emailsQ.error as Error)?.message || "Unknown error"} />
        ) : !rows.length ? (
          <EmptyState title="ไม่พบข้อมูล" message="ตรวจว่ามี email ในระบบแล้วหรือยัง (Stage 2-4)" />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Source</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((item) => (
                <tr key={item.id}>
                  <td>{item.place?.name || "-"}</td>
                  <td>{item.email}</td>
                  <td>{item.source}</td>
                  <td><Badge tone={(item.place?.status || "") === "DONE" ? "ok" : "neutral"}>{item.place?.status || "-"}</Badge></td>
                  <td>
                    <Button variant="secondary" onClick={() => nav(`/customer-details/${encodeURIComponent(item.place_id)}`)}>
                      Open
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

