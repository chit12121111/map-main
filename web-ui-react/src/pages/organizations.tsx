import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Button, Card, EmptyState, Input, PageHeader } from "../components/ui";

type DrillLevel = "province" | "district" | "category" | "places";
type GroupRow = { key: string; count: number; samplePlaceId: string };

export default function OrganizationsPage() {
  const nav = useNavigate();
  const [level, setLevel] = useState<DrillLevel>("province");
  const [selectedProvince, setSelectedProvince] = useState("");
  const [selectedDistrict, setSelectedDistrict] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [keyword, setKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [provinceFilter, setProvinceFilter] = useState("");
  const [districtFilter, setDistrictFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [dedupeRows, setDedupeRows] = useState(true);
  const placesQ = useQuery({ queryKey: ["org-places"], queryFn: () => api.getPlaces() });
  const places = placesQ.data?.data || [];
  const dedupeKey = (p: (typeof places)[number]) =>
    [
      (p.name || "").trim().toLowerCase(),
      (p.phone || "").trim().toLowerCase(),
      (p.address || "").trim().toLowerCase(),
      (p.website || "").trim().toLowerCase(),
    ].join("|");

  const provinceOptions = useMemo(
    () => Array.from(new Set(places.map((p) => p.province || "").filter(Boolean))).sort((a, b) => a.localeCompare(b, "th")),
    [places],
  );
  const districtOptions = useMemo(() => {
    const rows = provinceFilter ? places.filter((p) => (p.province || "") === provinceFilter) : places;
    return Array.from(new Set(rows.map((p) => p.district || "").filter(Boolean))).sort((a, b) => a.localeCompare(b, "th"));
  }, [places, provinceFilter]);
  const categoryOptions = useMemo(() => {
    const rows = places.filter((p) => {
      if (provinceFilter && (p.province || "") !== provinceFilter) return false;
      if (districtFilter && (p.district || "") !== districtFilter) return false;
      return true;
    });
    return Array.from(new Set(rows.map((p) => p.normalized_category || p.category || "").filter(Boolean))).sort((a, b) => a.localeCompare(b, "th"));
  }, [districtFilter, places, provinceFilter]);
  const filteredPlaces = useMemo(() => {
    const key = keyword.trim().toLowerCase();
    const base = places.filter((p) => {
      if (statusFilter && (p.status || "") !== statusFilter) return false;
      if (provinceFilter && (p.province || "") !== provinceFilter) return false;
      if (districtFilter && (p.district || "") !== districtFilter) return false;
      const normalizedCategory = p.normalized_category || p.category || "";
      if (categoryFilter && normalizedCategory !== categoryFilter) return false;
      if (!key) return true;
      const haystack = [p.name, p.category, p.normalized_category, p.phone, p.website, p.address, p.province, p.district]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(key);
    });
    if (!dedupeRows) return base;
    const seen = new Set<string>();
    return base.filter((p) => {
      const rowKey = dedupeKey(p);
      if (seen.has(rowKey)) return false;
      seen.add(rowKey);
      return true;
    });
  }, [places, keyword, statusFilter, provinceFilter, districtFilter, categoryFilter, dedupeRows]);

  const groupedRows = useMemo<GroupRow[]>(() => {
    const map = new Map<string, GroupRow>();
    const add = (key: string, placeId: string) => {
      const existing = map.get(key);
      if (existing) {
        existing.count += 1;
      } else {
        map.set(key, { key, count: 1, samplePlaceId: placeId });
      }
    };

    if (level === "province") {
      for (const p of filteredPlaces) add(p.province || "Uncategorized", p.place_id);
    } else if (level === "district") {
      for (const p of filteredPlaces) {
        if ((p.province || "Uncategorized") !== selectedProvince) continue;
        add(p.district || "Uncategorized", p.place_id);
      }
    } else if (level === "category") {
      for (const p of filteredPlaces) {
        if ((p.province || "Uncategorized") !== selectedProvince) continue;
        if ((p.district || "Uncategorized") !== selectedDistrict) continue;
        add(p.normalized_category || p.category || "Uncategorized", p.place_id);
      }
    }

    return [...map.values()].sort((a, b) => b.count - a.count);
  }, [filteredPlaces, level, selectedDistrict, selectedProvince]);

  const placeRows = useMemo(
    () =>
      filteredPlaces.filter((p) => {
        if ((p.province || "Uncategorized") !== selectedProvince) return false;
        if ((p.district || "Uncategorized") !== selectedDistrict) return false;
        if ((p.normalized_category || p.category || "Uncategorized") !== selectedCategory) return false;
        return true;
      }),
    [filteredPlaces, selectedCategory, selectedDistrict, selectedProvince],
  );

  const onDrill = (row: GroupRow) => {
    if (level === "province") {
      setSelectedProvince(row.key);
      setSelectedDistrict("");
      setSelectedCategory("");
      setLevel("district");
      return;
    }
    if (level === "district") {
      setSelectedDistrict(row.key);
      setSelectedCategory("");
      setLevel("category");
      return;
    }
    if (level === "category") {
      setSelectedCategory(row.key);
      setLevel("places");
    }
  };

  const onBack = () => {
    if (level === "places") {
      setLevel("category");
      setSelectedCategory("");
      return;
    }
    if (level === "category") {
      setLevel("district");
      setSelectedDistrict("");
      return;
    }
    if (level === "district") {
      setLevel("province");
      setSelectedProvince("");
    }
  };

  const breadcrumb = [
    "All",
    selectedProvince || null,
    selectedDistrict || null,
    selectedCategory || null,
  ]
    .filter(Boolean)
    .join(" > ");

  return (
    <div className="page-stack">
      <PageHeader title="Organizations" subtitle="Drill-down by province, district, category, and place" right={<Badge tone="info">{breadcrumb}</Badge>} />
      <Card title={level === "places" ? "Places" : "Groups"}>
        <div className="filter-grid">
          <Input placeholder="Search name/address/phone..." value={keyword} onChange={(e) => setKeyword(e.target.value)} />
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
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
            <label className="row gap-sm" style={{ color: "var(--muted)", fontSize: 13 }}>
              <input type="checkbox" checked={dedupeRows} onChange={(e) => setDedupeRows(e.target.checked)} />
              Hide duplicates
            </label>
            <Button
              variant="ghost"
              onClick={() => {
                setKeyword("");
                setStatusFilter("");
                setProvinceFilter("");
                setDistrictFilter("");
                setCategoryFilter("");
              }}
            >
              Reset filters
            </Button>
            <Badge tone="neutral">{filteredPlaces.length} places</Badge>
          </div>
        </div>
        <div className="toolbar">
          <Badge tone="neutral">Level: {level.toUpperCase()}</Badge>
          <div className="row gap-sm">
            <Button variant="ghost" onClick={onBack} disabled={level === "province"}>
              Back
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setLevel("province");
                setSelectedProvince("");
                setSelectedDistrict("");
                setSelectedCategory("");
                setKeyword("");
                setStatusFilter("");
                setProvinceFilter("");
                setDistrictFilter("");
                setCategoryFilter("");
              }}
              disabled={level === "province"}
            >
              Reset
            </Button>
          </div>
        </div>
        {placesQ.isPending ? (
          <EmptyState title="Loading groups..." message="กำลังดึงข้อมูลจาก API" />
        ) : placesQ.isError ? (
          <EmptyState title="โหลดข้อมูล groups ไม่สำเร็จ" message={(placesQ.error as Error)?.message || "Unknown error"} />
        ) : level !== "places" && !groupedRows.length ? (
          <EmptyState title="ยังไม่มีข้อมูลสำหรับจัดกลุ่ม" message="รัน pipeline แล้วลองใหม่" />
        ) : level === "places" && !placeRows.length ? (
          <EmptyState title="ไม่พบร้านในกลุ่มนี้" message="ลองย้อนกลับแล้วเลือกกลุ่มอื่น" />
        ) : level === "places" ? (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Category</th>
                <th>Status</th>
                <th>Phone</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {placeRows.map((p) => (
                <tr key={p.place_id}>
                  <td>{p.name}</td>
                  <td>{p.category || "-"}</td>
                  <td><Badge tone={(p.status || "") === "DONE" ? "ok" : "neutral"}>{p.status || "-"}</Badge></td>
                  <td>{p.phone || "-"}</td>
                  <td>
                    <Button variant="secondary" onClick={() => nav(`/customer-details/${encodeURIComponent(p.place_id)}`)}>
                      Open
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{level === "province" ? "Province" : level === "district" ? "District" : "Category"}</th>
                <th>Members</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {groupedRows.map((g) => (
                <tr key={g.key}>
                  <td>{g.key}</td>
                  <td><Badge tone="neutral">{g.count}</Badge></td>
                  <td>
                    <Button variant="secondary" onClick={() => onDrill(g)}>
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

