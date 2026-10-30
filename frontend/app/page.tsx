"use client";

import Link from "next/link";
import { AlertTriangle, ArrowRight, ArrowUpRight, Camera, CircleDot, Clock3, Factory, FileCheck2, MoveRight, ScanEye, ShieldAlert, Sparkles, Video, Waypoints } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, formatDate, prettyLabel, type Event, type Job, type Summary } from "@/lib/api";

export default function DashboardPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try {
      const [s, e, j] = await Promise.all([
        api<Summary>("/api/v1/reports/summary"), api<Event[]>("/api/v1/events?limit=5"), api<Job[]>("/api/v1/analyses?limit=4"),
      ]);
      setSummary(s); setEvents(e); setJobs(j); setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load dashboard data"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const cards = [
    { label: "Configured stations", value: summary?.stations ?? "—", note: "Across this organization", icon: Factory, tone: "copper" },
    { label: "Connected cameras", value: `${summary?.online_cameras ?? 0} / ${summary?.cameras ?? 0}`, note: "Only verified online states", icon: Camera, tone: "green" },
    { label: "Open alerts", value: summary?.open_events ?? "—", note: "Awaiting operator review", icon: AlertTriangle, tone: "red" },
    { label: "Queued analyses", value: summary?.queued_jobs ?? "—", note: "Waiting for a worker", icon: Clock3, tone: "amber" },
  ];
  const severityEntries = [
    { key: "critical", label: "Critical", color: "#c24e42" },
    { key: "high", label: "High", color: "#d78350" },
    { key: "warning", label: "Warning", color: "#dba142" },
    { key: "info", label: "Info", color: "#7d9b8a" },
  ];
  const total = severityEntries.reduce((acc, item) => acc + (summary?.events_by_severity?.[item.key] || 0), 0) || 1;

  return <div className="page-stack">
    <section className="page-heading heading-dashboard">
      <div><div className="eyebrow"><span className="eyebrow-line"/> OPERATIONS OVERVIEW</div><h1>Production intelligence<span className="copper-period">.</span></h1><p className="page-subtitle">Monitor station activity, review visual evidence, and keep quality events traceable.</p></div>
      <div className="heading-actions"><button className="button button-secondary" onClick={() => void refresh()}><ArrowUpRight size={16}/> Refresh data</button><Link href="/monitoring" className="button button-primary"><Video size={16}/> Analyze video</Link></div>
    </section>
    {error && <div className="alert-banner alert-error"><AlertTriangle size={17}/><span>{error}</span><button className="text-button" onClick={() => void refresh()}>Retry</button></div>}
    <section className="metric-grid" aria-label="Operations summary">
      {cards.map((card) => { const Icon = card.icon; return <article className="metric-card" key={card.label}><div className="metric-head"><span>{card.label}</span><span className={`metric-icon metric-${card.tone}`}><Icon size={18}/></span></div><div className="metric-value">{loading ? <span className="skeleton skeleton-number"/> : card.value}</div><div className="metric-foot"><span className="metric-foot-dot"/>{card.note}</div></article>; })}
    </section>
    <section className="dashboard-grid">
      <article className="panel panel-alerts">
        <div className="panel-header"><div><div className="panel-kicker">INSPECTION FEED</div><h2>Recent events</h2></div><Link href="/events" className="text-link">View all <ArrowRight size={15}/></Link></div>
        <div className="event-list">
          {loading ? <div className="empty-state"><span className="loader"/>Loading recent events…</div> : events.length === 0 ? <div className="empty-state"><div className="empty-icon"><FileCheck2 size={22}/></div><strong>No events to review</strong><span>Events from completed video analyses will appear here.</span><Link className="text-link" href="/monitoring">Start an analysis <ArrowRight size={14}/></Link></div> : events.map((event) => <div className="event-row" key={event.id}><div className={`event-severity-icon severity-${event.severity}`}><AlertTriangle size={17}/></div><div className="event-row-main"><div className="event-title-row"><strong>{event.summary}</strong><span className={`severity-tag severity-tag-${event.severity}`}>{prettyLabel(event.severity)}</span></div><div className="event-meta"><span>{prettyLabel(event.event_type)}</span><i/> <span>{Math.max(0, event.timestamp_seconds).toFixed(1)}s into video</span><i/><span>{formatDate(event.created_at)}</span></div></div><span className={`event-status status-${event.status}`}>{prettyLabel(event.status)}</span></div>)}
        </div>
      </article>
      <article className="panel panel-severity">
        <div className="panel-header"><div><div className="panel-kicker">QUALITY SIGNALS</div><h2>Severity distribution</h2></div><div className="panel-icon"><Waypoints size={18}/></div></div>
        <div className="severity-total"><strong>{summary?.total_events ?? 0}</strong><span>Total recorded events</span></div>
        <div className="severity-bar" aria-label="Severity distribution bar">{severityEntries.map((entry) => <span key={entry.key} style={{ width: `${(summary?.events_by_severity?.[entry.key] || 0) / total * 100}%`, background: entry.color }} title={`${entry.label}: ${summary?.events_by_severity?.[entry.key] || 0}`}/>)}</div>
        <div className="severity-legend">{severityEntries.map((entry) => <div className="legend-row" key={entry.key}><span className="legend-swatch" style={{ background: entry.color }}/><span>{entry.label}</span><strong>{summary?.events_by_severity?.[entry.key] || 0}</strong></div>)}</div>
        <div className="panel-note"><ShieldAlert size={15}/><span>Distribution across active organization inspection rules.</span></div>
      </article>
    </section>
    <section className="panel panel-jobs">
      <div className="panel-header"><div><div className="panel-kicker">PROCESSING QUEUE</div><h2>Recent analyses</h2></div><Link href="/monitoring" className="text-link">Open analysis workspace <ArrowRight size={15}/></Link></div>
      {loading ? <div className="empty-state"><span className="loader"/>Loading jobs…</div> : jobs.length === 0 ? <div className="empty-state compact"><div className="empty-icon"><ScanEye size={21}/></div><strong>No analysis jobs yet</strong><span>Upload a short clip to test a configured station.</span></div> : <div className="table-wrap"><table className="data-table"><thead><tr><th>JOB / VIDEO</th><th>PROVIDER</th><th>STATUS</th><th>CREATED</th><th>PROGRESS</th></tr></thead><tbody>{jobs.map((job) => <tr key={job.id}><td><div className="table-primary">{job.id.slice(0, 8).toUpperCase()}</div><div className="table-secondary">Video {job.video_id.slice(0, 8)}</div></td><td><span className="mono-tag">{job.provider_name}</span></td><td><span className={`job-status job-${job.status}`}><CircleDot size={12}/>{prettyLabel(job.status)}</span></td><td>{formatDate(job.created_at)}</td><td><div className="progress-cell"><div className="progress-track"><span style={{ width: `${job.progress}%` }}/></div><span>{job.progress}%</span></div></td></tr>)}</tbody></table></div>}
    </section>
    <section className="insight-strip"><div className="insight-icon"><Sparkles size={20}/></div><div><strong>Deterministic Quality Verification</strong><p>Automated visual rules with permanent evidence storage, audit-ready compliance logs and instant operator verification.</p></div><Link href="/stations" className="insight-link">Configure rules <MoveRight size={16}/></Link></section>
  </div>;
}
