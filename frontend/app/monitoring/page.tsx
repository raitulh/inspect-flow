"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  CircleHelp,
  Clock3,
  FileVideo,
  HardDriveUpload,
  RefreshCw,
  ScanEye,
  ShieldCheck,
  Upload,
  Video,
} from "lucide-react";
import { API_BASE, api, formatDate, prettyLabel, type Job, type Station } from "@/lib/api";

export default function MonitoringPage() {
  const [stations, setStations] = useState<Station[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stationId, setStationId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [fileKey, setFileKey] = useState(0);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, j] = await Promise.all([
        api<Station[]>("/api/v1/stations"),
        api<Job[]>("/api/v1/analyses?limit=20"),
      ]);
      setStations(s);
      setJobs(j);
      setSelectedJob((old) => (old ? j.find((item) => item.id === old.id) || old : j[0] || null));
      if (!stationId && s[0]) setStationId(s[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load monitoring data");
    }
  }, [stationId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void refresh();
    }, 3500);
    return () => window.clearInterval(timer);
  }, [refresh]);

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0] || null;
    setFile(next);
    setError("");
    setMessage("");
    if (next && next.size > 200 * 1024 * 1024) {
      setError("The selected file is larger than the default 200 MB limit.");
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!stationId) {
      setError("Create or select a station first.");
      return;
    }
    if (!file) {
      setError("Select a video file first.");
      return;
    }
    setSubmitting(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const uploaded = await api<{ id: string; original_filename: string }>(
        `/api/v1/videos?station_id=${encodeURIComponent(stationId)}`,
        { method: "POST", body: form }
      );
      const job = await api<Job>("/api/v1/analyses", {
        method: "POST",
        body: JSON.stringify({
          station_id: stationId,
          video_id: uploaded.id,
          provider_name: "opencv_rules",
        }),
      });
      setMessage(
        `Video “${uploaded.original_filename}” was accepted. Analysis job ${job.id
          .slice(0, 8)
          .toUpperCase()} is queued.`
      );
      setSelectedJob(job);
      setFile(null);
      setFileKey((value) => value + 1);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Video upload or analysis request failed");
    } finally {
      setSubmitting(false);
    }
  }

  const activeCount = jobs.filter((job) => ["queued", "running"].includes(job.status)).length;

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> VIDEO WORKSPACE
          </div>
          <h1>
            Analyze a station<span className="copper-period">.</span>
          </h1>
          <p className="page-subtitle">
            Upload production footage, run configured station rules, preview videos and review findings.
          </p>
        </div>
        <div className="heading-actions">
          <span className="inline-status">
            <span className={`health-dot ${activeCount > 0 ? "healthy" : ""}`} />
            {activeCount} active job{activeCount === 1 ? "" : "s"}
          </span>
          <button className="button button-secondary" onClick={() => void refresh()}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
      </section>

      {error && (
        <div className="alert-banner alert-error">
          <AlertCircle size={17} />
          <span>{error}</span>
          <button className="text-button" onClick={() => setError("")}>
            Dismiss
          </button>
        </div>
      )}
      {message && (
        <div className="alert-banner alert-success">
          <CheckCircle2 size={17} />
          <span>{message}</span>
          <button className="text-button" onClick={() => setMessage("")}>
            Dismiss
          </button>
        </div>
      )}

      <div className="monitoring-grid">
        <section className="panel upload-panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">NEW INSPECTION</div>
              <h2>Upload production video</h2>
            </div>
            <div className="panel-icon">
              <HardDriveUpload size={19} />
            </div>
          </div>
          <form className="stack-form" onSubmit={submit}>
            <label htmlFor="station-select">Target station</label>
            <select
              id="station-select"
              value={stationId}
              onChange={(event) => setStationId(event.target.value)}
              required
            >
              <option value="">Select a station</option>
              {stations.map((station) => (
                <option key={station.id} value={station.id}>
                  {station.name} · {station.code}
                </option>
              ))}
            </select>
            {!stations.length && (
              <div className="inline-hint">
                <CircleHelp size={15} /> No stations configured yet.{" "}
                <a href="/stations">Create a station</a> to continue.
              </div>
            )}
            <label>Video source</label>
            <input
              key={fileKey}
              className="visually-hidden"
              id="video-file"
              type="file"
              accept=".mp4,.mov,.avi,.mkv,.webm,video/*"
              onChange={chooseFile}
            />
            <label
              className={`dropzone ${file ? "dropzone-selected" : ""}`}
              htmlFor="video-file"
            >
              <div className="dropzone-icon">
                {file ? <FileVideo size={23} /> : <Upload size={23} />}
              </div>
              <strong>{file ? file.name : "Choose a video file"}</strong>
              <span>
                {file
                  ? `${(file.size / 1024 / 1024).toFixed(1)} MB · Ready for upload`
                  : "MP4, MOV, AVI, MKV or WebM"}
              </span>
              <em>Browse files</em>
            </label>
            <div className="upload-limit-row">
              <span>
                <HardDriveUpload size={14} /> Maximum file size: 200 MB by default
              </span>
              <span>CPU mode</span>
            </div>
            <div className="method-card">
              <div className="method-icon">
                <ScanEye size={18} />
              </div>
              <div>
                <strong>Automated station inspection</strong>
                <span>
                  High-speed frame sampling with adaptive lighting and anomaly heuristics.
                </span>
              </div>
              <span className="mode-tag" style={{ color: "#a5bea7", borderColor: "rgba(165,190,167,0.3)" }}>ACTIVE ENGINE</span>
            </div>
            <button
              className="button button-primary full-width"
              type="submit"
              disabled={submitting || !stations.length || !file}
            >
              {submitting ? (
                <>
                  <span className="button-spinner" /> Uploading and queueing…
                </>
              ) : (
                <>
                  Upload & queue analysis <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>
          <div className="privacy-note">
            <ShieldCheck size={15} />
            <span>Enterprise Storage · Station Isolated · Encrypted Local Vault</span>
          </div>
        </section>

        <section className="panel job-panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">ANALYSIS HISTORY</div>
              <h2>Recent processing jobs</h2>
            </div>
            <div className="panel-icon">
              <Clock3 size={18} />
            </div>
          </div>
          {jobs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">
                <Video size={23} />
              </div>
              <strong>No jobs yet</strong>
              <span>Uploaded video analyses will appear here.</span>
            </div>
          ) : (
            <div className="job-list">
              {jobs.map((job) => (
                <button
                  key={job.id}
                  className={`job-list-item ${selectedJob?.id === job.id ? "job-list-selected" : ""}`}
                  onClick={() => setSelectedJob(job)}
                >
                  <div className={`job-list-icon job-${job.status}`}>
                    {job.status === "completed" ? (
                      <CheckCircle2 size={17} />
                    ) : job.status === "failed" ? (
                      <AlertCircle size={17} />
                    ) : (
                      <Clock3 size={17} />
                    )}
                  </div>
                  <div className="job-list-main">
                    <div>
                      <strong>Analysis {job.id.slice(0, 8).toUpperCase()}</strong>
                      <span className={`job-status job-${job.status}`}>{prettyLabel(job.status)}</span>
                    </div>
                    <p>
                      Station {job.station_id.slice(0, 8)} · {formatDate(job.created_at)}
                    </p>
                    <div className="progress-track">
                      <span style={{ width: `${job.progress}%` }} />
                    </div>
                  </div>
                  <span className="job-percent">{job.progress}%</span>
                </button>
              ))}
            </div>
          )}

          {selectedJob && (
            <div className="selected-job-detail">
              <div className="panel-kicker">SELECTED JOB</div>
              <div className="selected-job-title">
                <strong>{selectedJob.id}</strong>
                <span className={`job-status job-${selectedJob.status}`}>
                  {prettyLabel(selectedJob.status)}
                </span>
              </div>

              {selectedJob.error_message && (
                <div className="job-error">
                  <AlertCircle size={15} />
                  {selectedJob.error_message}
                </div>
              )}

              {/* Video Player Preview if available */}
              {selectedJob.video_id && (
                <div
                  style={{
                    margin: "12px 0",
                    background: "#181f1d",
                    border: "1px solid #414a45",
                    borderRadius: "8px",
                    overflow: "hidden",
                  }}
                >
                  <video
                    ref={videoRef}
                    src={`${API_BASE}/api/v1/videos/${selectedJob.video_id}/content`}
                    controls
                    style={{ width: "100%", maxHeight: "240px", display: "block" }}
                    onError={(e) => {
                      (e.currentTarget as HTMLElement).style.display = "none";
                    }}
                  />
                </div>
              )}

              {selectedJob.result_summary && (
                <div className="result-summary">
                  <strong>Analysis Results</strong>
                  {(() => {
                    try {
                      const sum = JSON.parse(selectedJob.result_summary) as Record<string, unknown>;
                      return (
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px", margin: "10px 0" }}>
                          <div style={{ background: "#202724", padding: "8px 10px", borderRadius: "6px", border: "1px solid #37403c" }}>
                            <span style={{ fontSize: "9px", color: "#8a968e", display: "block" }}>Frames Sampled</span>
                            <strong style={{ fontSize: "14px", color: "#f6f0e6" }}>{String(sum.frames_sampled || "—")}</strong>
                          </div>
                          <div style={{ background: "#202724", padding: "8px 10px", borderRadius: "6px", border: "1px solid #37403c" }}>
                            <span style={{ fontSize: "9px", color: "#8a968e", display: "block" }}>Rules Evaluated</span>
                            <strong style={{ fontSize: "14px", color: "#f6f0e6" }}>{String(sum.rules_evaluated || "—")}</strong>
                          </div>
                          <div style={{ background: "#202724", padding: "8px 10px", borderRadius: "6px", border: "1px solid #37403c" }}>
                            <span style={{ fontSize: "9px", color: "#8a968e", display: "block" }}>Analysis Speed</span>
                            <strong style={{ fontSize: "14px", color: "#f6f0e6" }}>{sum.fps_reported ? `${sum.fps_reported} FPS` : "Real-time"}</strong>
                          </div>
                        </div>
                      );
                    } catch {
                      return null;
                    }
                  })()}
                  <div style={{ marginTop: "10px", display: "flex", gap: "10px", alignItems: "center" }}>
                    <a className="button button-primary" href={`/events?job_id=${selectedJob.id}`}>
                      Review findings <ArrowRight size={14} />
                    </a>
                  </div>
                </div>
              )}

              <div className="detail-meta">
                <span>Provider</span>
                <code>{selectedJob.provider_name}</code>
                <span>Completed</span>
                <strong>{formatDate(selectedJob.completed_at)}</strong>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
