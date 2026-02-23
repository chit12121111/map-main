import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Card, EmptyState, PageHeader } from "../components/ui";

export default function LogsPage() {
  const statusQ = useQuery({
    queryKey: ["pipeline-status"],
    queryFn: api.getPipelineStatus,
    refetchInterval: (q) => (q.state.data?.running ? 2000 : 5000),
  });

  const s = statusQ.data;

  return (
    <div className="page-stack">
      <PageHeader
        title="Logs"
        subtitle="Pipeline run status and live output"
        right={
          <Badge tone={s?.running ? "warn" : s?.ok ? "ok" : "neutral"}>
            {s?.running ? "Running" : s?.ok === true ? "Last Run: Success" : s?.ok === false ? "Last Run: Failed" : "Idle"}
          </Badge>
        }
      />

      <Card title="Run Status">
        {statusQ.isPending ? (
          <EmptyState title="Loading status..." message="กำลังอ่านสถานะ pipeline ล่าสุด" />
        ) : statusQ.isError ? (
          <EmptyState title="โหลดสถานะไม่สำเร็จ" message={(statusQ.error as Error)?.message || "Unknown error"} />
        ) : (
          <div className="kv-list">
            <div><span>Running</span><strong>{s?.running ? "Yes" : "No"}</strong></div>
            <div><span>Last Query</span><strong>{s?.last_query || "-"}</strong></div>
            <div><span>Started At</span><strong>{s?.started_at || "-"}</strong></div>
            <div><span>Finished At</span><strong>{s?.finished_at || "-"}</strong></div>
            <div><span>Rows</span><strong>{s?.rows ?? "-"}</strong></div>
            <div><span>Elapsed</span><strong>{s?.elapsed_ms ? `${Math.round(s.elapsed_ms / 1000)}s` : "-"}</strong></div>
          </div>
        )}
      </Card>

      <Card title="Output (tail)">
        {!s?.output?.length ? (
          <EmptyState title="No logs yet" message="เริ่มรัน Pipeline จากหน้า Dashboard เพื่อดู output ที่นี่" />
        ) : (
          <div className="runner-output">
            <pre>{s.output.join("\n")}</pre>
          </div>
        )}
      </Card>
    </div>
  );
}
