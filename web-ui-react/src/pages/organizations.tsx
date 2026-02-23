import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Button, Card, EmptyState, PageHeader } from "../components/ui";

type GroupRow = { key: string; count: number; samplePlaceId: string };

export default function OrganizationsPage() {
  const nav = useNavigate();
  const placesQ = useQuery({ queryKey: ["org-places"], queryFn: () => api.getPlaces() });

  const groups = useMemo<GroupRow[]>(() => {
    const map = new Map<string, GroupRow>();
    for (const p of placesQ.data?.data || []) {
      const key = p.category || "Uncategorized";
      const existing = map.get(key);
      if (existing) {
        existing.count += 1;
      } else {
        map.set(key, { key, count: 1, samplePlaceId: p.place_id });
      }
    }
    return [...map.values()].sort((a, b) => b.count - a.count);
  }, [placesQ.data]);

  return (
    <div className="page-stack">
      <PageHeader title="Organizations" subtitle="Grouped overview by category" right={<Badge tone="info">Category Analytics</Badge>} />
      <Card title="Groups">
        {!groups.length ? (
          <EmptyState title="ยังไม่มีข้อมูลสำหรับจัดกลุ่ม" message="รัน pipeline แล้วลองใหม่" />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Group</th>
                <th>Members</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <tr key={g.key}>
                  <td>{g.key}</td>
                  <td><Badge tone="neutral">{g.count}</Badge></td>
                  <td>
                    <Button variant="secondary" onClick={() => nav(`/customer-details/${encodeURIComponent(g.samplePlaceId)}`)}>
                      Drill down
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

