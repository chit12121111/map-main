import type { PropsWithChildren, ReactNode } from "react";
import type { ButtonHTMLAttributes, InputHTMLAttributes } from "react";

export function PageHeader(props: { title: string; subtitle?: string; right?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{props.title}</h1>
        {props.subtitle ? <p>{props.subtitle}</p> : null}
      </div>
      {props.right ? <div className="page-header-right">{props.right}</div> : null}
    </div>
  );
}

export function Card(props: PropsWithChildren<{ title?: string; actions?: ReactNode; className?: string; compact?: boolean }>) {
  return (
    <section className={`card ${props.compact ? "card-compact" : ""} ${props.className || ""}`.trim()}>
      {(props.title || props.actions) && (
        <header className="card-header">
          {props.title ? <h3>{props.title}</h3> : <span />}
          {props.actions}
        </header>
      )}
      <div className="card-body">{props.children}</div>
    </section>
  );
}

export function StatCard(props: { label: string; value: string | number; hint?: string; trend?: string }) {
  return (
    <div className="stat-card">
      <div className="stat-top">
        <div className="stat-label">{props.label}</div>
        {props.trend ? <span className="stat-trend">{props.trend}</span> : null}
      </div>
      <div className="stat-value">{props.value}</div>
      {props.hint ? <div className="stat-hint">{props.hint}</div> : null}
    </div>
  );
}

export function Badge(props: { tone?: "ok" | "warn" | "bad" | "neutral" | "info"; children: ReactNode }) {
  return <span className={`badge ${props.tone || "neutral"}`}>{props.children}</span>;
}

export function Button(
  props: ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: "primary" | "secondary" | "ghost" | "danger";
    block?: boolean;
  },
) {
  const { variant = "secondary", block = false, className, ...rest } = props;
  return <button className={`btn btn-${variant} ${block ? "btn-block" : ""} ${className || ""}`.trim()} {...rest} />;
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} />;
}

export function EmptyState(props: { title: string; message: string }) {
  return (
    <div className="empty-state">
      <strong>{props.title}</strong>
      <p>{props.message}</p>
    </div>
  );
}

