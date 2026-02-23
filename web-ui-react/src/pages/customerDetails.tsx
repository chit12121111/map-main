import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Card, EmptyState, PageHeader } from "../components/ui";

export default function CustomerDetailsPage() {
  const params = useParams<{ placeId?: string }>();
  const placeId = params.placeId;

  const placeQ = useQuery({
    queryKey: ["place", placeId],
    queryFn: () => api.getPlace(placeId!),
    enabled: Boolean(placeId),
  });
  const emailsQ = useQuery({
    queryKey: ["place-emails", placeId],
    queryFn: () => api.getEmails({ placeId }),
    enabled: Boolean(placeId),
  });
  const urlsQ = useQuery({
    queryKey: ["urls"],
    queryFn: () => api.getDiscoveredUrls(),
  });

  if (!placeId) {
    return (
      <div className="page-stack">
        <PageHeader title="Customer Details" subtitle="เลือก customer จากหน้า Customers ก่อน" />
        <EmptyState title="ยังไม่ได้เลือก customer" message="ไปหน้า Customers แล้วกด Open" />
      </div>
    );
  }

  return (
    <div className="page-stack">
      <PageHeader title="Customer Details" subtitle={`place_id: ${placeId}`} right={<Badge tone={(placeQ.data?.status || "") === "DONE" ? "ok" : "neutral"}>{placeQ.data?.status || "N/A"}</Badge>} />

      <div className="split-grid">
        <Card title="Profile">
          {placeQ.isPending ? (
            <EmptyState title="Loading profile..." message="กำลังดึงข้อมูล place" />
          ) : placeQ.isError ? (
            <EmptyState title="โหลดข้อมูล place ไม่สำเร็จ" message={(placeQ.error as Error)?.message || "Unknown error"} />
          ) : !placeQ.data ? (
            <EmptyState title="ไม่พบข้อมูล place" message="อาจถูกลบหรือยังไม่ sync" />
          ) : (
            <div className="kv-list">
              <div><span>Name</span><strong>{placeQ.data.name}</strong></div>
              <div><span>Category</span><strong>{placeQ.data.category || "-"}</strong></div>
              <div><span>Phone</span><strong>{placeQ.data.phone || "-"}</strong></div>
              <div><span>Website</span><strong>{placeQ.data.website || "-"}</strong></div>
              <div><span>Address</span><strong>{placeQ.data.address || "-"}</strong></div>
            </div>
          )}
        </Card>
        <Card title="Emails">
          {emailsQ.isPending ? (
            <EmptyState title="Loading emails..." message="กำลังดึงข้อมูลอีเมล" />
          ) : emailsQ.isError ? (
            <EmptyState title="โหลดข้อมูลอีเมลไม่สำเร็จ" message={(emailsQ.error as Error)?.message || "Unknown error"} />
          ) : !(emailsQ.data?.data || []).length ? (
            <EmptyState title="ยังไม่พบอีเมล" message="รอ Stage 2-4 ประมวลผลเพิ่มเติม" />
          ) : (
            <ul className="simple-list">
              {(emailsQ.data?.data || []).map((e) => (
                <li key={e.id}>
                  {e.email} <small>({e.source})</small>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Discovered URLs">
        {urlsQ.isPending ? (
          <EmptyState title="Loading URLs..." message="กำลังดึง discovered URLs" />
        ) : urlsQ.isError ? (
          <EmptyState title="โหลด URLs ไม่สำเร็จ" message={(urlsQ.error as Error)?.message || "Unknown error"} />
        ) : (
          <ul className="simple-list">
            {(urlsQ.data?.data || [])
              .filter((u) => u.place_id === placeId)
              .map((u) => (
                <li key={u.id}>
                  {u.url} <small>[{u.url_type} / {u.status}]</small>
                </li>
              ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

