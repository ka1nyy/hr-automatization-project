import { Link } from 'react-router-dom';

export type ChartDatum = { label: string; value: number; color: string; detail?: string; to?: string };

export function DonutChart({ data, centerValue, centerLabel, ariaLabel }: { data: ChartDatum[]; centerValue: string; centerLabel: string; ariaLabel: string }) {
  const total = Math.max(1, data.reduce((sum, item) => sum + item.value, 0));
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return <div className="dashboard-donut-layout">
    <div className="dashboard-donut" role="img" aria-label={ariaLabel}>
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle className="dashboard-donut-track" cx="50" cy="50" r={radius} />
        {data.filter((item) => item.value > 0).map((item) => {
          const length = item.value / total * circumference;
          const currentOffset = offset;
          offset += length;
          return <circle key={item.label} className="dashboard-donut-segment" cx="50" cy="50" r={radius} style={{ stroke: item.color }} strokeDasharray={`${Math.max(0, length - 2)} ${circumference}`} strokeDashoffset={-currentOffset} />;
        })}
      </svg>
      <span><strong>{centerValue}</strong><small>{centerLabel}</small></span>
    </div>
    <div className="dashboard-chart-legend">{data.map((item) => item.to ? <Link key={item.label} to={item.to}><i style={{ background: item.color }} /><span><strong>{item.label}</strong>{item.detail && <small>{item.detail}</small>}</span><b>{item.value}</b></Link> : <div key={item.label}><i style={{ background: item.color }} /><span><strong>{item.label}</strong>{item.detail && <small>{item.detail}</small>}</span><b>{item.value}</b></div>)}</div>
  </div>;
}

export function BarChart({ data, ariaLabel }: { data: ChartDatum[]; ariaLabel: string }) {
  const max = Math.max(1, ...data.map((item) => item.value));
  const column = (item: ChartDatum) => <><div><span style={{ height: `${Math.max(item.value ? 12 : 2, item.value / max * 100)}%`, background: item.color }}><b>{item.value}</b></span></div><small>{item.label}</small></>;
  return <div className="dashboard-bar-chart" role="group" aria-label={ariaLabel}>
    <div className="dashboard-bar-plot">{data.map((item) => item.to ? <Link key={item.label} to={item.to} className="dashboard-bar-column" aria-label={`${item.label}: ${item.value}`}>{column(item)}</Link> : <div key={item.label} className="dashboard-bar-column">{column(item)}</div>)}</div>
    <div className="dashboard-bar-axis"><span>0</span><span>{Math.ceil(max / 2)}</span><span>{max}</span></div>
  </div>;
}
