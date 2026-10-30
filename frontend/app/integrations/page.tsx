"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  BellRing,
  Camera,
  CheckCircle2,
  Cpu,
  Eye,
  EyeOff,
  Factory,
  HardDrive,
  PlugZap,
  RefreshCw,
  Send,
  ShieldAlert,
  Trash2,
  Wifi,
} from "lucide-react";
import { API_BASE, api, type Camera as CameraSource, type Station } from "@/lib/api";

type PLCStatus = {
  mode: string;
  configured: boolean;
  connected: boolean;
  outputs_enabled: boolean;
  host?: string | null;
  port: number;
  note: string;
};
type PLCResult = {
  connected?: boolean;
  accepted?: boolean;
  simulated?: boolean;
  message: string;
  mode?: string;
};

type WebhookTestResult = {
  configured: boolean;
  success?: boolean;
  url?: string;
  message: string;
};

type CleanupResult = {
  freed_bytes: number;
  freed_mb: number;
  videos_removed: number;
  evidence_removed: number;
  max_age_days: number;
};

export default function IntegrationsPage() {
  const [cameras, setCameras] = useState<CameraSource[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [plc, setPlc] = useState<PLCStatus | null>(null);
  const [stationId, setStationId] = useState("");
  const [cameraName, setCameraName] = useState("Assembly RTSP camera");
  const [sourceType, setSourceType] = useState("rtsp");
  const [sourceUri, setSourceUri] = useState("");
  const [stopPhrase, setStopPhrase] = useState("");
  const [safetyAck, setSafetyAck] = useState(false);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [activeStreamCameraId, setActiveStreamCameraId] = useState<string | null>(null);
  const [cleanupDays, setCleanupDays] = useState(30);

  const refresh = useCallback(async () => {
    try {
      const [c, s, p] = await Promise.all([
        api<CameraSource[]>("/api/v1/cameras"),
        api<Station[]>("/api/v1/stations"),
        api<PLCStatus>("/api/v1/integrations/plc/status"),
      ]);
      setCameras(c);
      setStations(s);
      setPlc(p);
      setStationId((old) => (old && s.some((item) => item.id === old) ? old : s[0]?.id || ""));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load integration status");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function createCamera(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResult("");
    try {
      const created = await api<CameraSource>("/api/v1/cameras", {
        method: "POST",
        body: JSON.stringify({
          station_id: stationId,
          name: cameraName,
          source_type: sourceType,
          source_uri: sourceUri,
        }),
      });
      setResult(`Camera “${created.name}” registered. Start the camera-worker service to process live frames.`);
      setSourceUri("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not register camera");
    } finally {
      setBusy(false);
    }
  }

  async function testCamera(camera: CameraSource) {
    setBusy(true);
    setError("");
    setResult("");
    try {
      const tested = await api<{ status: string; message: string }>(
        `/api/v1/cameras/${camera.id}/test-connection`,
        { method: "POST" }
      );
      setResult(`${camera.name}: ${tested.status} — ${tested.message}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Camera test failed");
    } finally {
      setBusy(false);
    }
  }

  async function testPLC() {
    setBusy(true);
    setError("");
    setResult("");
    try {
      const response = await api<PLCResult>("/api/v1/integrations/plc/test", { method: "POST" });
      setResult(response.message);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "PLC test failed");
    } finally {
      setBusy(false);
    }
  }

  async function testWebhook() {
    setBusy(true);
    setError("");
    setResult("");
    try {
      const resp = await api<WebhookTestResult>("/api/v1/integrations/webhook-test", { method: "POST" });
      setResult(`Webhook test: ${resp.message}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Webhook test failed");
    } finally {
      setBusy(false);
    }
  }

  async function runStorageCleanup() {
    if (!window.confirm(`Clean up video files and evidence older than ${cleanupDays} days?`)) return;
    setBusy(true);
    setError("");
    setResult("");
    try {
      const res = await api<CleanupResult>(`/api/v1/storage/cleanup?days=${cleanupDays}`, { method: "POST" });
      setResult(
        `Storage cleanup complete! Freed ${res.freed_mb} MB (${res.videos_removed} raw videos, ${res.evidence_removed} stale evidence frames removed).`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Storage cleanup failed");
    } finally {
      setBusy(false);
    }
  }

  async function requestStop() {
    setBusy(true);
    setError("");
    setResult("");
    try {
      const response = await api<PLCResult>("/api/v1/integrations/plc/machine-stop-request", {
        method: "POST",
        body: JSON.stringify({ confirmation: stopPhrase, safety_acknowledged: safetyAck }),
      });
      setResult(response.message);
      setStopPhrase("");
      setSafetyAck(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stop request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> DEVICE & CONTROL CONNECTIVITY
          </div>
          <h1>
            Integrations<span className="copper-period">.</span>
          </h1>
          <p className="page-subtitle">
            Connect authorized RTSP cameras, stream live feeds, test outbound webhooks, manage retention and inspect the PLC adapter.
          </p>
        </div>
        <div className="heading-actions">
          <button className="button button-secondary" onClick={() => void refresh()}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
      </section>

      {error && (
        <div className="alert-banner alert-error">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}
      {result && (
        <div className="alert-banner alert-success">
          <CheckCircle2 size={16} />
          <span>{result}</span>
          <button className="text-button" onClick={() => setResult("")}>
            Dismiss
          </button>
        </div>
      )}

      <div className="config-columns">
        <section className="panel config-panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">CAMERA INPUTS</div>
              <h2>Register a camera</h2>
              <p className="panel-description">RTSP sources are polled by the separate camera-worker process.</p>
            </div>
            <div className="panel-icon">
              <Camera size={18} />
            </div>
          </div>
          <form className="stack-form" onSubmit={createCamera}>
            <label htmlFor="camera-station">Target station</label>
            <select id="camera-station" value={stationId} onChange={(e) => setStationId(e.target.value)} required>
              <option value="">Select a station</option>
              {stations.map((station) => (
                <option key={station.id} value={station.id}>
                  {station.name} · {station.code}
                </option>
              ))}
            </select>
            <label htmlFor="camera-name">Camera name</label>
            <input id="camera-name" value={cameraName} onChange={(e) => setCameraName(e.target.value)} required maxLength={160} />
            <label htmlFor="camera-type">Source type</label>
            <select id="camera-type" value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
              <option value="rtsp">RTSP / RTSPS</option>
              <option value="webcam">Local webcam device</option>
            </select>
            <label htmlFor="camera-uri">
              {sourceType === "rtsp" ? "RTSP URI (without embedded credentials)" : "Device index"}
            </label>
            <input
              id="camera-uri"
              value={sourceUri}
              onChange={(e) => setSourceUri(e.target.value)}
              required
              placeholder={sourceType === "rtsp" ? "rtsp://192.168.1.20:554/stream1" : "0"}
            />
            <button
              className="button button-primary full-width"
              type="submit"
              disabled={busy || !stationId || !sourceUri.trim()}
            >
              <Wifi size={16} /> Register camera
            </button>
          </form>
          <div className="privacy-note">
            <ShieldAlert size={15} />
            <span>
              Use private LAN camera addresses only. Do not embed passwords in RTSP URLs.
            </span>
          </div>
        </section>

        <section className="panel config-panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">PLC ADAPTER</div>
              <h2>Machine interface</h2>
            </div>
            <div className="panel-icon">
              <PlugZap size={18} />
            </div>
          </div>
          {plc ? (
            <div className="simple-list">
              <div className="simple-list-item">
                <span className="simple-list-icon">
                  <Activity size={17} />
                </span>
                <span>
                  <strong>Mode</strong>
                  <small>{plc.mode}</small>
                </span>
                <span className={`tiny-state ${plc.mode === "simulation" ? "tiny-state-on" : ""}`}>
                  {plc.mode === "simulation" ? "SIMULATED" : "HARDWARE"}
                </span>
              </div>
              <div className="simple-list-item">
                <span className="simple-list-icon">
                  <Wifi size={17} />
                </span>
                <span>
                  <strong>Endpoint</strong>
                  <small>
                    {plc.host || "No host configured"}:{plc.port}
                  </small>
                </span>
              </div>
              <div className="simple-list-item">
                <span className="simple-list-icon">
                  <ShieldAlert size={17} />
                </span>
                <span>
                  <strong>PLC outputs</strong>
                  <small>{plc.outputs_enabled ? "Enabled by deployment configuration" : "Disabled (safe default)"}</small>
                </span>
                <span className={`tiny-state ${!plc.outputs_enabled ? "tiny-state-on" : ""}`}>
                  {plc.outputs_enabled ? "ENABLED" : "OFF"}
                </span>
              </div>
            </div>
          ) : (
            <div className="list-empty">Loading PLC status…</div>
          )}
          <p className="panel-description" style={{ padding: "0 20px" }}>
            {plc?.note || "PLC adapter status"}
          </p>
          <div style={{ padding: "0 20px 14px" }}>
            <button className="button button-secondary full-width" onClick={() => void testPLC()} disabled={busy}>
              <PlugZap size={16} /> Test PLC connection
            </button>
          </div>
          <div className="privacy-note">
            <ShieldAlert size={15} />
            <span>Detection events never stop machinery automatically. The adapter sends only a momentary confirmed request.</span>
          </div>
        </section>
      </div>

      {/* Live Camera Streaming Section */}
      <section className="panel rule-config-panel">
        <div className="panel-header">
          <div>
            <div className="panel-kicker">LIVE CAMERA FEEDS</div>
            <h2>Registered camera sources & live stream</h2>
            <p className="panel-description">
              The camera-worker polls frames at the configured cadence and caches live previews.
            </p>
          </div>
          <div className="panel-icon">
            <Factory size={18} />
          </div>
        </div>
        <div className="simple-list">
          {cameras.length ? (
            cameras.map((camera) => (
              <div
                key={camera.id}
                style={{
                  border: "1px solid rgba(255, 255, 255, 0.05)",
                  borderRadius: "8px",
                  marginBottom: "8px",
                  overflow: "hidden",
                  background: "rgba(0, 0, 0, 0.1)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px 14px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <span className="simple-list-icon">
                      <Camera size={17} />
                    </span>
                    <div>
                      <strong>{camera.name}</strong>
                      <div style={{ fontSize: "9px", color: "#8a968e" }}>
                        {camera.source_type.toUpperCase()} · {camera.status}
                        {camera.last_error ? ` · ${camera.last_error}` : ""}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <button
                      className="button button-secondary"
                      onClick={() =>
                        setActiveStreamCameraId((curr) => (curr === camera.id ? null : camera.id))
                      }
                      disabled={camera.source_type === "uploaded_video"}
                    >
                      {activeStreamCameraId === camera.id ? <EyeOff size={14} /> : <Eye size={14} />}
                      {activeStreamCameraId === camera.id ? "Hide Feed" : "Watch Live"}
                    </button>
                    <button
                      className="button button-secondary"
                      onClick={() => void testCamera(camera)}
                      disabled={busy || camera.source_type === "uploaded_video"}
                    >
                      Test frame
                    </button>
                  </div>
                </div>

                {/* Inline Live Video Stream */}
                {activeStreamCameraId === camera.id && (
                  <div
                    style={{
                      background: "#161c1a",
                      borderTop: "1px solid rgba(255, 255, 255, 0.08)",
                      padding: "16px",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                    }}
                  >
                    <div
                      style={{
                        position: "relative",
                        maxWidth: "720px",
                        width: "100%",
                        borderRadius: "8px",
                        overflow: "hidden",
                        border: "1px solid #414a45",
                        boxShadow: "0 8px 30px rgba(0,0,0,0.5)",
                      }}
                    >
                      <img
                        src={`${API_BASE}/api/v1/cameras/${camera.id}/stream`}
                        alt={`Live stream for ${camera.name}`}
                        style={{ width: "100%", height: "auto", display: "block" }}
                        onError={(e) => {
                          e.currentTarget.style.display = "none";
                          const errBox = e.currentTarget.parentElement?.querySelector(".stream-error");
                          if (errBox) (errBox as HTMLElement).style.display = "flex";
                        }}
                      />
                      <div
                        className="stream-error"
                        style={{
                          display: "none",
                          padding: "40px 20px",
                          flexDirection: "column",
                          alignItems: "center",
                          justifyContent: "center",
                          color: "#d7867e",
                          gap: "8px",
                        }}
                      >
                        <ShieldAlert size={24} />
                        <span>Camera stream is currently connecting or offline.</span>
                        <small style={{ color: "#8a968e" }}>
                          Ensure the camera-worker process is running and the RTSP URI is reachable.
                        </small>
                      </div>
                      <div
                        style={{
                          position: "absolute",
                          top: "10px",
                          left: "10px",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                          background: "rgba(0, 0, 0, 0.7)",
                          padding: "4px 8px",
                          borderRadius: "4px",
                          fontSize: "9px",
                          color: "#afc8b3",
                        }}
                      >
                        <span className="health-dot healthy" /> LIVE MONITOR
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="list-empty">No camera sources have been registered.</div>
          )}
        </div>
      </section>

      {/* Outbound Webhook & Retention Section */}
      <div className="config-columns">
        <section className="panel config-panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">EXTERNAL NOTIFICATIONS</div>
              <h2>Outbound alerts & webhooks</h2>
              <p className="panel-description">
                Notify plant managers, Slack, Discord or MES systems on high/critical events.
              </p>
            </div>
            <div className="panel-icon">
              <BellRing size={18} />
            </div>
          </div>
          <div style={{ padding: "18px 20px", display: "grid", gap: "12px" }}>
            <div style={{ fontSize: "11px", color: "#aab3ac", lineHeight: "1.6" }}>
              Configure <code>WEBHOOK_URL</code> and optional <code>WEBHOOK_SECRET</code> in your environment file to dispatch signed HMAC-SHA256 payloads whenever an inspection event is raised.
            </div>
            <button
              className="button button-secondary full-width"
              onClick={() => void testWebhook()}
              disabled={busy}
            >
              <Send size={15} /> Send test webhook ping
            </button>
          </div>
        </section>

        <section className="panel config-panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">DISK RETENTION</div>
              <h2>Storage cleanup & pruning</h2>
              <p className="panel-description">
                Purge completed raw videos and stale resolved evidence to conserve disk space.
              </p>
            </div>
            <div className="panel-icon">
              <HardDrive size={18} />
            </div>
          </div>
          <div style={{ padding: "18px 20px", display: "grid", gap: "12px" }}>
            <label htmlFor="cleanup-days" style={{ fontSize: "11px", color: "#d0d8d0" }}>
              Purge files older than (days):
            </label>
            <input
              id="cleanup-days"
              type="number"
              min={1}
              max={365}
              value={cleanupDays}
              onChange={(e) => setCleanupDays(parseInt(e.target.value) || 30)}
              style={{
                width: "100%",
                background: "#272f2c",
                border: "1px solid #46504a",
                borderRadius: "7px",
                padding: "8px 12px",
                color: "#fff",
              }}
            />
            <button
              className="button button-danger-ghost full-width"
              onClick={() => void runStorageCleanup()}
              disabled={busy}
            >
              <Trash2 size={15} /> Run retention storage cleanup
            </button>
          </div>
        </section>
      </div>

      <section className="panel rule-config-panel">
        <div className="panel-header">
          <div>
            <div className="panel-kicker">PLC BOUNDARY</div>
            <h2>Manual machine stop request</h2>
            <p className="panel-description">
              Dedicated PLC coil interface requiring explicit operator confirmation and safety protocol verification.
            </p>
          </div>
          <div className="panel-icon">
            <Cpu size={18} />
          </div>
        </div>
        <div className="rule-builder-grid">
          <div className="stack-form">
            <label htmlFor="stop-phrase">Type REQUEST_STOP to confirm</label>
            <input
              id="stop-phrase"
              value={stopPhrase}
              onChange={(e) => setStopPhrase(e.target.value)}
              placeholder="REQUEST_STOP"
            />
            <label className="check-row">
              <input
                type="checkbox"
                checked={safetyAck}
                onChange={(e) => setSafetyAck(e.target.checked)}
              />{" "}
              Operator safety verification acknowledged.
            </label>
            <button
              className="button button-secondary full-width"
              onClick={() => void requestStop()}
              disabled={busy || stopPhrase !== "REQUEST_STOP" || !safetyAck}
            >
              Dispatch momentary stop-request bit
            </button>
          </div>
          <div className="rule-explainer">
            <div className="rule-explainer-card">
              <div className="rule-explainer-icon">
                <ShieldAlert size={20} />
              </div>
              <strong>Industrial safety boundary</strong>
              <p>
                Modbus communication operates in simulation mode unless hardware outputs are commissioned. Commands are recorded with full operator audit traceability.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
