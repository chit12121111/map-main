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

export function DonutChartCard(props: {
  data: ChartItem[];
  innerRadius?: number;
  outerRadius?: number;
  onSelect?: (name: string) => void;
  selectedName?: string;
}) {
  return (
    <div className="chart-wrap" role="img" aria-label="Donut chart">
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie
            data={props.data}
            dataKey="value"
            nameKey="name"
            innerRadius={props.innerRadius ?? 65}
            outerRadius={props.outerRadius ?? 95}
            paddingAngle={2}
            onClick={(entry) => props.onSelect?.(entry.name)}
          >
            {props.data.map((_, idx) => (
              <Cell key={`cell-${idx}`} fill={palette[idx % palette.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
      <div className="chart-filter-list" aria-label="Donut filters">
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

