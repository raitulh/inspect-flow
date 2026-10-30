"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowDownToLine,
  CheckCircle2,
  FileChartColumn,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { API_BASE, api, prettyLabel, type Summary } from "@/lib/api";

type Quality = {
  events_by_type: { event_type: string; count: number }[];
  model_metrics: null;
  note: string;
};
type StationReport = {
  station_id: string;
  name: string;
  code: string;
  events: number;
  open_events: number;
};

export default function ReportsPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [quality, setQuality] = useState<Quality | null>(null);
  const [stations, setStations] = useState<StationReport[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api<Summary>("/api/v1/reports/summary"),
      api<Quality>("/api/v1/reports/quality"),
      api<StationReport[]>("/api/v1/reports/stations"),
    ])
      .then(([s, q, st]) => {
        setSummary(s);
        setQuality(q);
        setStations(st);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load reports"));
  }, []);

  const rows = quality?.events_by_type || [];
  const max = Math.max(1, ...rows.map((row) => row.count));

  const totalEvents = summary?.total_events ?? 0;
  const openEvents = summary?.open_events ?? 0;
  const resolvedEvents = Math.max(0, totalEvents - openEvents);
  const resolutionRate = totalEvents > 0 ? Math.round((resolvedEvents / totalEvents) * 100) : 100;

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> REPORTING
          </div>
          <h1>
            Quality intelligence<span className="copper-period">.</span>
          </h1>
          <p className="page-subtitle">
            Real-time quality KPIs, station review loads, and audit logs across active production lines.
          </p>
        </div>
        <div className="heading-actions">
          <a
            className="button button-primary"
            href={`${API_BASE}/api/v1/reports/export.csv`}
            target="_blank"
            rel="noreferrer"
          >
            <ArrowDownToLine size={16} /> Export CSV Report
          </a>
        </div>
      </section>

      {error && (
        <div className="alert-banner alert-error">
          <AlertTriangle size={16} />
          {error}
        </div>
      )}

      <section className="metric-grid">
        <article className="metric-card">
          <div className="metric-head">
            <span>Total Recorded Events</span>
            <span className="metric-icon metric-copper">
              <FileChartColumn size={18} />
            </span>
          </div>
          <div className="metric-value">{summary?.total_events ?? "—"}</div>
          <div className="metric-foot">All detected anomalies</div>
        </article>
        <article className="metric-card">
          <div className="metric-head">
            <span>Open Quality Alerts</span>
            <span className="metric-icon metric-red">
              <AlertTriangle size={18} />
            </span>
          </div>
          <div className="metric-value">{summary?.open_events ?? "—"}</div>
          <div className="metric-foot">Pending operator review</div>
        </article>
        <article className="metric-card">
          <div className="metric-head">
            <span>Resolution Rate</span>
            <span className="metric-icon metric-green">
              <TrendingUp size={18} />
            </span>
          </div>
          <div className="metric-value">{resolutionRate}%</div>
          <div className="metric-foot">{resolvedEvents} of {totalEvents} resolved</div>
        </article>
        <article className="metric-card">
          <div className="metric-head">
            <span>Online Camera Feeds</span>
            <span className="metric-icon metric-amber">
              <ShieldCheck size={18} />
            </span>
          </div>
          <div className="metric-value">
            {summary ? `${summary.online_cameras}/${summary.cameras}` : "—"}
          </div>
          <div className="metric-foot">Active inspection streams</div>
        </article>
      </section>

      <section className="dashboard-grid report-grid">
        <article className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">EVENT BREAKDOWN</div>
              <h2>Events by category</h2>
            </div>
            <div className="panel-icon">
              <FileChartColumn size={18} />
            </div>
          </div>
          {rows.length ? (
            <div className="horizontal-bars">
              {rows.map((row) => (
                <div className="horizontal-bar-row" key={row.event_type}>
                  <div className="bar-row-label">
                    <span>{prettyLabel(row.event_type)}</span>
                    <strong>{row.count}</strong>
                  </div>
                  <div className="progress-track">
                    <span style={{ width: `${(row.count / max) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">
                <FileChartColumn size={20} />
              </div>
              <strong>No event data yet</strong>
              <span>Inspection events will appear here after video analysis.</span>
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">COMPLIANCE & VERIFICATION</div>
              <h2>Audit readiness</h2>
            </div>
            <div className="panel-icon">
              <ShieldCheck size={18} />
            </div>
          </div>
          <div className="evaluation-empty">
            <div className="evaluation-icon" style={{ background: "rgba(67, 115, 93, 0.15)", color: "#8fa58e" }}>
              <ShieldCheck size={22} />
            </div>
            <strong>Traceable Quality Verification</strong>
            <p>
              Every detection event preserves the exact frame evidence, rule configuration version, and immutable timestamp.
            </p>
            <div className="evaluation-checks">
              <span>
                <CheckCircle2 size={15} /> 100% Deterministic Rule Traceability
              </span>
              <span>
                <CheckCircle2 size={15} /> Complete Resolution Audit Log Stored
              </span>
              <span>
                <CheckCircle2 size={15} /> Exportable CSV & Quality History
              </span>
            </div>
          </div>
        </article>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-kicker">STATION PERFORMANCE</div>
            <h2>Station event summary</h2>
          </div>
        </div>
        {stations.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>STATION</th>
                  <th>CODE</th>
                  <th>TOTAL EVENTS</th>
                  <th>OPEN EVENTS</th>
                  <th>REVIEW LOAD</th>
                </tr>
              </thead>
              <tbody>
                {stations.map((s) => (
                  <tr key={s.station_id}>
                    <td>
                      <div className="table-primary">{s.name}</div>
                      <div className="table-secondary">{s.station_id.slice(0, 8)}</div>
                    </td>
                    <td>
                      <code>{s.code}</code>
                    </td>
                    <td>{s.events}</td>
                    <td>{s.open_events}</td>
                    <td>
                      <div className="progress-cell">
                        <div className="progress-track">
                          <span
                            style={{
                              width: `${s.events ? (s.open_events / s.events) * 100 : 0}%`,
                            }}
                          />
                        </div>
                        <span>
                          {s.events ? Math.round((s.open_events / s.events) * 100) : 0}% open
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state compact">
            <span>No station data configured</span>
          </div>
        )}
      </section>
    </div>
  );
}
