"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCheck,
  CheckCircle2,
  CircleHelp,
  Filter,
  RefreshCw,
  Search,
  Volume2,
  VolumeX,
  XCircle,
  Radio,
} from "lucide-react";
import { API_BASE, api, formatDate, prettyLabel, type Event, type Station } from "@/lib/api";

function playAlertChime() {
  try {
    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = "sine";
    const now = ctx.currentTime;
    osc.frequency.setValueAtTime(880, now);
    osc.frequency.setValueAtTime(1320, now + 0.12);
    gain.gain.setValueAtTime(0.12, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc.start(now);
    osc.stop(now + 0.36);
  } catch {
    // Audio might be blocked by browser policy before first interaction
  }
}

export default function EventsPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [status, setStatus] = useState("open");
  const [severity, setSeverity] = useState("");
  const [stationId, setStationId] = useState("");
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selected, setSelected] = useState<Event | null>(null);
  const [audioAlerts, setAudioAlerts] = useState(false);
  const [liveStreamConnected, setLiveStreamConnected] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const query = new URLSearchParams();
      if (status) query.set("status", status);
      if (severity) query.set("severity", severity);
      if (stationId) query.set("station_id", stationId);
      query.set("limit", "100");
      const [e, s] = await Promise.all([
        api<Event[]>(`/api/v1/events?${query.toString()}`),
        api<Station[]>("/api/v1/stations"),
      ]);
      setEvents(e);
      setStations(s);
      setSelected((old) => (old ? e.find((x) => x.id === old.id) || null : null));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load events");
    }
  }, [status, severity, stationId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Real-time EventSource (SSE) listener
  useEffect(() => {
    let sse: EventSource | null = null;
    try {
      sse = new EventSource(`${API_BASE}/api/v1/events/stream`, { withCredentials: true });
      sse.addEventListener("connected", () => {
        setLiveStreamConnected(true);
      });
      sse.addEventListener("detection_event", (msg) => {
        try {
          const newEvent = JSON.parse(msg.data) as Event;
          setEvents((prev) => [newEvent, ...prev.filter((x) => x.id !== newEvent.id)]);
          if (audioAlerts && (newEvent.severity === "critical" || newEvent.severity === "warning")) {
            playAlertChime();
          }
        } catch {
          void refresh();
        }
      });
      sse.onerror = () => {
        setLiveStreamConnected(false);
      };
    } catch {
      setLiveStreamConnected(false);
    }
    return () => {
      sse?.close();
    };
  }, [audioAlerts, refresh]);

  const action = useCallback(
    async (event: Event, kind: "acknowledge" | "resolve" | "false-positive") => {
      setBusyId(event.id);
      setError("");
      setNotice("");
      try {
        const path = kind === "false-positive" ? "mark-false-positive" : kind;
        let body: string | undefined;
        if (kind === "resolve") body = JSON.stringify({ note: window.prompt("Resolution note (optional):") || "" });
        if (kind === "false-positive") {
          const reason = window.prompt("Why is this a false positive?");
          if (!reason?.trim()) {
            setBusyId("");
            return;
          }
          body = JSON.stringify({ reason });
        }
        await api(`/api/v1/events/${event.id}/${path}`, { method: "POST", ...(body ? { body } : {}) });
        setNotice(
          `Event ${event.id.slice(0, 8).toUpperCase()} marked ${
            kind === "false-positive" ? "as false positive" : kind === "acknowledge" ? "acknowledged" : "resolved"
          }.`
        );
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Event action failed");
      } finally {
        setBusyId("");
      }
    },
    [refresh]
  );

  const filtered = events.filter((event) =>
    `${event.summary} ${event.event_type} ${event.id}`.toLowerCase().includes(search.toLowerCase())
  );
  const stationName = (id: string) => stations.find((station) => station.id === id)?.name || id.slice(0, 8);

  // Keyboard navigation shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(tag)) return;

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        setSelected((curr) => {
          if (!curr && filtered[0]) return filtered[0];
          const idx = filtered.findIndex((x) => x.id === curr?.id);
          return idx >= 0 && idx < filtered.length - 1 ? filtered[idx + 1] : curr;
        });
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        setSelected((curr) => {
          if (!curr && filtered[0]) return filtered[0];
          const idx = filtered.findIndex((x) => x.id === curr?.id);
          return idx > 0 ? filtered[idx - 1] : curr;
        });
      } else if (e.key.toLowerCase() === "a" && selected && selected.status === "open") {
        e.preventDefault();
        void action(selected, "acknowledge");
      } else if (
        e.key.toLowerCase() === "r" &&
        selected &&
        !["resolved", "false_positive"].includes(selected.status)
      ) {
        e.preventDefault();
        void action(selected, "resolve");
      } else if (
        e.key.toLowerCase() === "f" &&
        selected &&
        !["resolved", "false_positive"].includes(selected.status)
      ) {
        e.preventDefault();
        void action(selected, "false-positive");
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [filtered, selected, action]);

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> QUALITY REVIEW
          </div>
          <h1>
            Event intelligence<span className="copper-period">.</span>
          </h1>
          <p className="page-subtitle">
            Review visual findings with evidence, context and an auditable resolution workflow.
          </p>
        </div>
        <div className="heading-actions">
          {liveStreamConnected && (
            <span className="inline-status" style={{ color: "#8fa58e", fontSize: "10.5px" }}>
              <Radio size={13} style={{ animation: "pulse 2s infinite" }} /> Live SSE Connected
            </span>
          )}
          <button
            type="button"
            className="button button-secondary"
            onClick={() => {
              const next = !audioAlerts;
              setAudioAlerts(next);
              if (next) playAlertChime();
            }}
            title="Play two-tone chime when warning or critical events occur"
          >
            {audioAlerts ? <Volume2 size={15} style={{ color: "#c58b61" }} /> : <VolumeX size={15} />}
            <span>Chime: {audioAlerts ? "On" : "Off"}</span>
          </button>
          <button className="button button-secondary" onClick={() => void refresh()}>
            <RefreshCw size={16} /> Refresh
          </button>
          <a
            className="button button-primary"
            href={`${API_BASE}/api/v1/reports/export.csv`}
            target="_blank"
            rel="noreferrer"
          >
            Export CSV <ArrowRight size={15} />
          </a>
        </div>
      </section>

      {error && (
        <div className="alert-banner alert-error">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}
      {notice && (
        <div className="alert-banner alert-success">
          <CheckCircle2 size={16} />
          <span>{notice}</span>
          <button className="text-button" onClick={() => setNotice("")}>
            Dismiss
          </button>
        </div>
      )}

      <section className="panel events-panel">
        <div className="filter-toolbar">
          <div className="search-box">
            <Search size={16} />
            <input
              placeholder="Search events or identifiers…"
              aria-label="Search events"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="filter-control">
            <Filter size={15} />
            <select
              aria-label="Filter status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">All statuses</option>
              <option value="open">Open</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="resolved">Resolved</option>
              <option value="false_positive">False positive</option>
            </select>
          </div>
          <div className="filter-control">
            <select
              aria-label="Filter severity"
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
            >
              <option value="">All severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </div>
          <div className="filter-control">
            <select
              aria-label="Filter station"
              value={stationId}
              onChange={(e) => setStationId(e.target.value)}
            >
              <option value="">All stations</option>
              {stations.map((s) => (
                <option value={s.id} key={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <span className="mono-tag" style={{ marginLeft: "auto", fontSize: "9px" }}>
            ⌨ Shortcuts: [J/K] Navigate · [A] Ack · [R] Resolve · [F] False Positive
          </span>
        </div>

        {filtered.length === 0 ? (
          <div className="empty-state event-empty">
            <div className="empty-icon">
              <CheckCheck size={23} />
            </div>
            <strong>No events match these filters</strong>
            <span>Try changing the status filter or run an analysis on a configured station.</span>
            <button
              className="button button-secondary"
              onClick={() => {
                setStatus("");
                setSeverity("");
                setStationId("");
                setSearch("");
              }}
            >
              Clear filters
            </button>
          </div>
        ) : (
          <div className="event-review-layout">
            <div className="event-review-list">
              {filtered.map((event) => (
                <button
                  key={event.id}
                  className={`review-event ${selected?.id === event.id ? "review-event-selected" : ""}`}
                  onClick={() => setSelected(event)}
                >
                  <span className={`event-severity-icon severity-${event.severity}`}>
                    <AlertTriangle size={16} />
                  </span>
                  <span className="review-event-content">
                    <strong>{event.summary}</strong>
                    <small>
                      {stationName(event.station_id)} · {formatDate(event.created_at)}
                    </small>
                    <span className="review-event-tags">
                      <span className={`severity-tag severity-tag-${event.severity}`}>
                        {prettyLabel(event.severity)}
                      </span>
                      <span className={`event-status status-${event.status}`}>
                        {prettyLabel(event.status)}
                      </span>
                    </span>
                  </span>
                  <ArrowRight size={15} className="review-arrow" />
                </button>
              ))}
            </div>

            {selected && (
              <div className="event-detail-pane">
                <div className="detail-topline">
                  <span className="panel-kicker">EVENT DETAIL</span>
                  <span className="mono-tag">{selected.id.slice(0, 12).toUpperCase()}</span>
                </div>
                <h2>{selected.summary}</h2>
                <div className="detail-tags">
                  <span className={`severity-tag severity-tag-${selected.severity}`}>
                    {prettyLabel(selected.severity)}
                  </span>
                  <span className={`event-status status-${selected.status}`}>
                    {prettyLabel(selected.status)}
                  </span>
                </div>

                <div className="evidence-preview">
                  <img
                    src={`${API_BASE}/api/v1/events/${selected.id}/evidence`}
                    alt={`Evidence for ${selected.summary}`}
                    onError={(event) => {
                      event.currentTarget.style.display = "none";
                      event.currentTarget.parentElement?.classList.add("evidence-unavailable");
                    }}
                  />
                  <div className="evidence-placeholder">
                    <CircleHelp size={21} />
                    <span>Evidence image is unavailable for this event.</span>
                  </div>
                  <span className="evidence-time">
                    {Math.max(0, selected.timestamp_seconds).toFixed(2)}s
                  </span>
                </div>

                <div className="detail-facts">
                  <div>
                    <span>Station</span>
                    <strong>{stationName(selected.station_id)}</strong>
                  </div>
                  <div>
                    <span>Event type</span>
                    <strong>{prettyLabel(selected.event_type)}</strong>
                  </div>
                  <div>
                    <span>Recorded</span>
                    <strong>{formatDate(selected.created_at)}</strong>
                  </div>
                  <div>
                    <span>Model / rule</span>
                    <strong>
                      {selected.model_version}
                      {selected.rule_version ? ` · r${selected.rule_version}` : ""}
                    </strong>
                  </div>
                </div>

                <div className="detail-explanation">
                  <strong>Evidence context</strong>
                  <p>
                    {(() => {
                      try {
                        const detail = JSON.parse(selected.details_json) as {
                          note?: string;
                          observation?: string;
                        };
                        return `${prettyLabel(detail.observation || selected.event_type)}. ${
                          detail.note || "Review the evidence against the configured inspection rule."
                        }`;
                      } catch {
                        return "Review the evidence against the configured inspection rule.";
                      }
                    })()}
                  </p>
                </div>

                {selected.resolution_note && (
                  <div className="resolution-note">
                    <strong>Resolution note</strong>
                    <p>{selected.resolution_note}</p>
                  </div>
                )}
                {selected.false_positive_reason && (
                  <div className="resolution-note">
                    <strong>False-positive reason</strong>
                    <p>{selected.false_positive_reason}</p>
                  </div>
                )}

                {!["resolved", "false_positive"].includes(selected.status) && (
                  <div className="event-action-buttons">
                    {selected.status === "open" && (
                      <button
                        className="button button-secondary"
                        disabled={busyId === selected.id}
                        onClick={() => void action(selected, "acknowledge")}
                      >
                        <CheckCheck size={15} /> Acknowledge (A)
                      </button>
                    )}
                    <button
                      className="button button-primary"
                      disabled={busyId === selected.id}
                      onClick={() => void action(selected, "resolve")}
                    >
                      <CheckCircle2 size={15} /> Resolve (R)
                    </button>
                    <button
                      className="button button-danger-ghost"
                      disabled={busyId === selected.id}
                      onClick={() => void action(selected, "false-positive")}
                    >
                      <XCircle size={15} /> False positive (F)
                    </button>
                  </div>
                )}

                <a
                  className="text-link evidence-download"
                  href={`${API_BASE}/api/v1/events/${selected.id}/evidence`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open evidence image <ArrowRight size={14} />
                </a>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
