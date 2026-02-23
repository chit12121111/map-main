import { useMemo } from "react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  Legend,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Bar,
} from "recharts";

type ChartItem = { name: string; value: number };

const palette = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#64748b"];

function colorByName(name: string, idx: number): string {
  const normalized = name.toUpperCase();
  if (normalized === "DONE") return "#10b981";
  if (normalized === "FAILED") return "#ef4444";
  if (normalized === "NEW") return "#f59e0b";
  return palette[idx % palette.length];
}

export function DonutChartCard(props: {
  data: ChartItem[];
  innerRadius?: number;
  outerRadius?: number;
  onSelect?: (name: string) => void;
  selectedName?: string;
  showAllButton?: boolean;
  repeatSelectFallbackName?: string;
}) {
  const selectedItem = useMemo(
    () => props.data.find((item) => item.name === props.selectedName),
    [props.data, props.selectedName],
  );
  const totalValue = useMemo(
    () => props.data.reduce((sum, item) => sum + item.value, 0),
    [props.data],
  );
  const displayData = selectedItem ? [selectedItem] : props.data;
  const onSelectName = (name: string) => {
    if (props.selectedName === name && props.repeatSelectFallbackName) {
      props.onSelect?.(props.repeatSelectFallbackName);
      return;
    }
    props.onSelect?.(name);
  };

  return (
    <div className="chart-wrap" role="img" aria-label="Donut chart">
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie
            data={displayData}
            dataKey="value"
            nameKey="name"
            innerRadius={props.innerRadius ?? 65}
            outerRadius={props.outerRadius ?? 95}
            paddingAngle={2}
            labelLine={false}
            label={({ x, y, value }) => (
              <text
                x={x}
                y={y}
                fill="#111827"
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={12}
                fontWeight={700}
              >
                {value}
              </text>
            )}
            onClick={(entry) => onSelectName(entry.name)}
          >
            {displayData.map((item, idx) => (
              <Cell key={`cell-${item.name}-${idx}`} fill={colorByName(item.name, idx)} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
      <div className="chart-filter-list" aria-label="Donut filters">
        {props.showAllButton ? (
          <button
            key="all"
            type="button"
            className={`chart-filter-btn ${props.selectedName ? "" : "active"}`}
            onClick={() => props.onSelect?.("")}
          >
            ALL ({totalValue})
          </button>
        ) : null}
        {props.data.map((item) => (
          <button
            key={item.name}
            type="button"
            className={`chart-filter-btn ${props.selectedName === item.name ? "active" : ""}`}
            onClick={() => onSelectName(item.name)}
          >
            {item.name} ({item.value})
          </button>
        ))}
      </div>
    </div>
  );
}

export function SimpleBarChartCard(props: {
  data: ChartItem[];
  onSelect?: (name: string) => void;
  selectedName?: string;
}) {
  return (
    <div className="chart-wrap" role="img" aria-label="Bar chart">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={props.data} margin={{ top: 12, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Bar
            dataKey="value"
            fill="#2563eb"
            radius={[8, 8, 0, 0]}
            onClick={(entry) => {
              if (entry?.name) props.onSelect?.(entry.name);
            }}
          />
        </BarChart>
      </ResponsiveContainer>
      <div className="chart-filter-list" aria-label="Bar filters">
        {props.data.map((item) => (
          <button
            key={item.name}
            type="button"
            className={`chart-filter-btn ${props.selectedName === item.name ? "active" : ""}`}
            onClick={() => props.onSelect?.(item.name)}
          >
            {item.name} ({item.value})
          </button>
        ))}
      </div>
    </div>
  );
}

