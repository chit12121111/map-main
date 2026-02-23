import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Button, Card, EmptyState, PageHeader } from "../components/ui";

export default function CustomerDetailsPage() {
  const nav = useNavigate();
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
      <PageHeader
        title="Customer Details"
        subtitle={`place_id: ${placeId}`}
        right={
          <div className="row gap-sm">
            <Badge tone={(placeQ.data?.status || "") === "DONE" ? "ok" : placeQ.data?.status === "FAILED" ? "bad" : "neutral"}>
              {placeQ.data?.status || "N/A"}
            </Badge>
            <Button variant="secondary" onClick={() => nav(-1)}>Back</Button>
          </div>
        }
      />

      <div className="customer-details-wrap">
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
              <div><span>Category</span><strong>{placeQ.data.normalized_category || placeQ.data.category || "-"}</strong></div>
              <div><span>Phone</span><strong>{placeQ.data.phone || "-"}</strong></div>
              <div>
                <span>Email</span>
                <strong>
                  {(emailsQ.data?.data || []).length ? (
                    (emailsQ.data?.data || []).map((item) => (
                      <div key={item.id}>
                        <a href={`mailto:${item.email}`}>{item.email}</a>
                      </div>
                    ))
                  ) : emailsQ.isPending ? (
                    "Loading..."
                  ) : (
                    "-"
                  )}
                </strong>
              </div>
              <div>
                <span>Website</span>
                <strong>
                  {placeQ.data.website ? (
                    <a href={placeQ.data.website} target="_blank" rel="noreferrer">{placeQ.data.website}</a>
                  ) : (
                    "-"
                  )}
                </strong>
              </div>
              <div>
                <span>Google Maps</span>
                <strong>
                  {placeQ.data.google_maps_url ? (
                    <a href={placeQ.data.google_maps_url} target="_blank" rel="noreferrer">Open map</a>
                  ) : (
                    "-"
                  )}
                </strong>
              </div>
              <div><span>Address</span><strong>{placeQ.data.address || "-"}</strong></div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

