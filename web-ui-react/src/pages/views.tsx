import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Button, Card, EmptyState, Input, PageHeader, StatCard } from "../components/ui";
import { DonutChartCard, SimpleBarChartCard } from "../components/charts";

type CustomerRow = {
  key: string;
  place_id: string;
  name: string;
  email: string;
  source: string;
  status: string;
  place: {
    province?: string | null;
    district?: string | null;
    category?: string | null;
    normalized_category?: string | null;
  } | null;
};

export default function ViewsPage() {
  const nav = useNavigate();
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [provinceFilter, setProvinceFilter] = useState("");
  const [districtFilter, setDistrictFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const statsQ = useQuery({ queryKey: ["stats"], queryFn: api.getStats });
  const placesQ = useQuery({ queryKey: ["places-all"], queryFn: () => api.getPlaces() });
  const emailsQ = useQuery({ queryKey: ["emails-with-place"], queryFn: () => api.getEmails({ includePlace: true }) });

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
  const customerRows = useMemo<CustomerRow[]>(() => {
    const emailRows: CustomerRow[] = (emailsQ.data?.data || []).map((item) => ({
      key: `email-${item.id}`,
      place_id: item.place_id,
      name: item.place?.name || "-",
      email: item.email,
      source: item.source,
      status: item.place?.status || "UNKNOWN",
      place: item.place || null,
    }));
    const emailPlaceIds = new Set(emailRows.map((item) => item.place_id));
    const failedWithoutEmail: CustomerRow[] = (placesQ.data?.data || [])
      .filter((p) => (p.status || "") === "FAILED" && !emailPlaceIds.has(p.place_id))
      .map((p) => ({
        key: `failed-${p.place_id}`,
        place_id: p.place_id,
        name: p.name || "-",
        email: "-",
        source: "NO_EMAIL",
        status: p.status || "FAILED",
        place: p,
      }));
    const list = [...emailRows, ...failedWithoutEmail];
    const keyword = q.trim().toLowerCase();
    return list.filter((item) => {
      if (sourceFilter && item.source !== sourceFilter) return false;
      if (status && item.status !== status) return false;
      const placeProvince = item.place?.province || "";
      if (provinceFilter && placeProvince !== provinceFilter) return false;
      const placeDistrict = item.place?.district || "";
      if (districtFilter && placeDistrict !== districtFilter) return false;
      const normalizedCategory = item.place?.normalized_category || item.place?.category || "";
      if (categoryFilter && normalizedCategory !== categoryFilter) return false;
      if (!keyword) return true;
      const name = item.name.toLowerCase();
      const email = item.email.toLowerCase();
      const source = item.source.toLowerCase();
      const province = (item.place?.province || "").toLowerCase();
      const district = (item.place?.district || "").toLowerCase();
      const category = (item.place?.normalized_category || item.place?.category || "").toLowerCase();
      return (
        name.includes(keyword) ||
        email.includes(keyword) ||
        source.includes(keyword) ||
        province.includes(keyword) ||
        district.includes(keyword) ||
        category.includes(keyword)
      );
    });
  }, [emailsQ.data, placesQ.data, q, sourceFilter, status, provinceFilter, districtFilter, categoryFilter]);
  const placeRows = placesQ.data?.data || [];
  const sourceOptions = useMemo(
    () => Array.from(new Set(customerRows.map((e) => e.source).filter(Boolean))).sort(),
    [customerRows],
  );
  const provinceOptions = useMemo(
    () => Array.from(new Set(placeRows.map((p) => p.province || "").filter(Boolean))).sort((a, b) => a.localeCompare(b, "th")),
    [placeRows],
  );
  const districtOptions = useMemo(() => {
    const rows = provinceFilter ? placeRows.filter((p) => (p.province || "") === provinceFilter) : placeRows;
    return Array.from(new Set(rows.map((p) => p.district || "").filter(Boolean))).sort((a, b) => a.localeCompare(b, "th"));
  }, [placeRows, provinceFilter]);
  const categoryOptions = useMemo(() => {
    const rows = placeRows.filter((p) => {
      if (provinceFilter && (p.province || "") !== provinceFilter) return false;
      if (districtFilter && (p.district || "") !== districtFilter) return false;
      return true;
    });
    return Array.from(new Set(rows.map((p) => p.normalized_category || p.category || "").filter(Boolean))).sort((a, b) => a.localeCompare(b, "th"));
  }, [districtFilter, placeRows, provinceFilter]);
  const filteredCount = customerRows.length;

  return (
    <div className="page-stack">
      <PageHeader title="Views" subtitle="ภาพรวมข้อมูล scrape และรายชื่อลูกค้าในหน้าเดียว" right={<Badge tone="info">Unified Workspace</Badge>} />
      <div className="kpi-grid">
        <StatCard label="Places" value={statsQ.data?.total_places ?? 0} />
        <StatCard label="Emails" value={statsQ.data?.total_emails ?? 0} />
        <StatCard label="Discovered URLs" value={statsQ.data?.total_discovered ?? 0} />
        <StatCard label="Success Rate" value={successRate} />
      </div>
      <div className="split-grid">
        <Card title="Place Status (click to filter table)" actions={status ? <Button variant="ghost" onClick={() => setStatus("")}>Clear</Button> : null}>
          <DonutChartCard
            data={statusData}
            onSelect={setStatus}
            selectedName={status}
            showAllButton
            repeatSelectFallbackName="NEW"
          />
        </Card>
        <Card title="Discovered URL Types">
          <SimpleBarChartCard data={typeData} />
        </Card>
      </div>
      <Card title="Customer Table">
        <div className="filter-grid">
          <Input placeholder="Search name/email/source..." value={q} onChange={(e) => setQ(e.target.value)} />
          <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
            <option value="">All sources</option>
            {sourceOptions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="NEW">NEW</option>
            <option value="DONE">DONE</option>
            <option value="FAILED">FAILED</option>
          </select>
          <select value={provinceFilter} onChange={(e) => setProvinceFilter(e.target.value)}>
            <option value="">All provinces</option>
            {provinceOptions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
          <select value={districtFilter} onChange={(e) => setDistrictFilter(e.target.value)}>
            <option value="">All districts</option>
            {districtOptions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
          <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
            <option value="">All categories</option>
            {categoryOptions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
          <div className="row gap-sm">
            <Button
              variant="ghost"
              onClick={() => {
                setQ("");
                setSourceFilter("");
                setStatus("");
                setProvinceFilter("");
                setDistrictFilter("");
                setCategoryFilter("");
              }}
            >
              Reset filters
            </Button>
            <Badge tone="neutral">{filteredCount} result{filteredCount === 1 ? "" : "s"}</Badge>
          </div>
        </div>
        {emailsQ.isPending || placesQ.isPending ? (
          <EmptyState title="Loading customers..." message="กำลังดึงข้อมูลจาก API" />
        ) : emailsQ.isError || placesQ.isError ? (
          <EmptyState
            title="โหลดข้อมูลลูกค้าไม่สำเร็จ"
            message={(emailsQ.error as Error)?.message || (placesQ.error as Error)?.message || "Unknown error"}
          />
        ) : !customerRows.length ? (
          <EmptyState title="ไม่พบข้อมูล" message="ตรวจว่ามี email ในระบบแล้วหรือยัง (Stage 2-4)" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Province</th>
                  <th>District</th>
                  <th>Category</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {customerRows.map((item) => (
                  <tr key={item.key}>
                    <td>{item.name || "-"}</td>
                    <td>{item.email}</td>
                    <td>{item.place?.province || "-"}</td>
                    <td>{item.place?.district || "-"}</td>
                    <td>{item.place?.normalized_category || item.place?.category || "-"}</td>
                    <td>
                      <button type="button" className="source-link-btn" onClick={() => setSourceFilter(item.source)}>
                        {item.source}
                      </button>
                    </td>
                    <td>
                      <Badge tone={item.status === "DONE" ? "ok" : item.status === "FAILED" ? "bad" : "neutral"}>
                        {item.status || "-"}
                      </Badge>
                    </td>
                    <td>
                      <Button variant="secondary" onClick={() => nav(`/customer-details/${encodeURIComponent(item.place_id)}`)}>
                        Open
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

