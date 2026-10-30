"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertCircle, ArrowRight, CheckCircle2, ChevronRight, CircleHelp, Factory, Plus, Save, SlidersHorizontal } from "lucide-react";
import { api, prettyLabel, type Rule, type Site, type Station, type User } from "@/lib/api";
import VisualZoneDrawer from "@/components/VisualZoneDrawer";

const defaultColorConfig = JSON.stringify({
  zone: [0.15, 0.15, 0.85, 0.85],
  hsv_lower: [100, 80, 50],
  hsv_upper: [130, 255, 255],
  min_pixel_ratio: 0.015,
  min_consecutive: 3,
}, null, 2);
const defaultMotionConfig = JSON.stringify({ inactivity_seconds: 5, mean_difference_threshold: 2.0 }, null, 2);
const defaultSurfaceConfig = JSON.stringify({ zone: [0.05, 0.05, 0.95, 0.95], threshold: 24, min_area: 8, min_length_px: 8, min_aspect_ratio: 2.0, score_threshold: 0.25 }, null, 2);
const defaultObjectConfig = JSON.stringify({ mode: "detect", model_path: "", confidence: 0.35, iou: 0.45, image_size: 512, target_classes: ["scratch", "crack", "missing_component"], min_consecutive: 3 }, null, 2);

export default function StationsPage() {
  const [sites, setSites] = useState<Site[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedSite, setSelectedSite] = useState("");
  const [selectedStation, setSelectedStation] = useState("");
  const [siteName, setSiteName] = useState("Main Production Floor");
  const [siteCode, setSiteCode] = useState("MAIN");
  const [stationName, setStationName] = useState("Assembly Station 01");
  const [stationCode, setStationCode] = useState("ASSY-01");
  const [ruleName, setRuleName] = useState("Blue component presence");
  const [ruleType, setRuleType] = useState("color_presence");
  const [ruleConfig, setRuleConfig] = useState(defaultColorConfig);
  const [severity, setSeverity] = useState("warning");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [s, st, r, me] = await Promise.all([
        api<Site[]>("/api/v1/sites"), api<Station[]>("/api/v1/stations"), api<Rule[]>("/api/v1/inspection-rules"), api<User>("/api/v1/auth/me"),
      ]);
      setSites(s); setStations(st); setRules(r); setUser(me); setError("");
      setSelectedSite((old) => old && s.some((x) => x.id === old) ? old : s[0]?.id || "");
      setSelectedStation((old) => old && st.some((x) => x.id === old) ? old : st[0]?.id || "");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load station configuration"); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  async function createSite(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    try {
      const site = await api<Site>("/api/v1/sites", { method: "POST", body: JSON.stringify({ name: siteName, code: siteCode, location: "" }) });
      setNotice(`Site “${site.name}” created.`); setSelectedSite(site.id); await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create site"); }
    finally { setSaving(false); }
  }

  async function createStation(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    try {
      const station = await api<Station>("/api/v1/stations", { method: "POST", body: JSON.stringify({ site_id: selectedSite, name: stationName, code: stationCode, description: "Configured inspection station" }) });
      setNotice(`Station “${station.name}” created.`); setSelectedStation(station.id); await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create station"); }
    finally { setSaving(false); }
  }

  async function createRule(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    try {
      let config: Record<string, unknown>;
      try { config = JSON.parse(ruleConfig) as Record<string, unknown>; }
      catch { throw new Error("Rule configuration must be valid JSON."); }
      const rule = await api<Rule>("/api/v1/inspection-rules", { method: "POST", body: JSON.stringify({ station_id: selectedStation, name: ruleName, rule_type: ruleType, config, severity, is_enabled: true }) });
      setNotice(`Inspection rule “${rule.name}” created.`); await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create inspection rule"); }
    finally { setSaving(false); }
  }

  const canConfigure = user && ["owner", "admin", "engineer"].includes(user.role);
  const displayedStations = stations.filter((station) => !selectedSite || station.site_id === selectedSite);
  const selectedStationRules = rules.filter((rule) => rule.station_id === selectedStation);

  return <div className="page-stack">
    <section className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> CONFIGURATION</div><h1>Stations & inspection rules<span className="copper-period">.</span></h1><p className="page-subtitle">Set up the production hierarchy and define explicit inspection behavior for a known assembly.</p></div><div className="heading-actions"><span className="inline-status"><span className="health-dot healthy"/>{stations.length} configured</span></div></section>
    {error && <div className="alert-banner alert-error"><AlertCircle size={16}/><span>{error}</span><button className="text-button" onClick={() => setError("")}>Dismiss</button></div>}{notice && <div className="alert-banner alert-success"><CheckCircle2 size={16}/><span>{notice}</span><button className="text-button" onClick={() => setNotice("")}>Dismiss</button></div>}
    {!canConfigure && user && <div className="alert-banner alert-info"><SlidersHorizontal size={16}/><span>Your role is read-only for station configuration. Ask an administrator or engineer to change stations and inspection rules.</span></div>}
    <div className="config-columns">
      <section className="panel config-panel"><div className="panel-header"><div><div className="panel-kicker">STEP 01</div><h2>Production sites</h2></div><div className="panel-icon"><Factory size={18}/></div></div>
        <form className="stack-form" onSubmit={createSite}><label htmlFor="site-name">Site name</label><input id="site-name" required maxLength={160} value={siteName} onChange={(e) => setSiteName(e.target.value)} placeholder="Main production floor"/><label htmlFor="site-code">Site code</label><input id="site-code" required maxLength={64} pattern="[A-Za-z0-9_-]+" value={siteCode} onChange={(e) => setSiteCode(e.target.value)} placeholder="MAIN"/><button className="button button-secondary full-width" type="submit" disabled={!canConfigure || saving}><Plus size={16}/> Create site</button></form>
        <div className="config-list-label">EXISTING SITES <span>{sites.length}</span></div><div className="simple-list">{sites.length ? sites.map((site) => <button key={site.id} className={`simple-list-item ${selectedSite === site.id ? "simple-list-active" : ""}`} onClick={() => setSelectedSite(site.id)}><span className="simple-list-icon"><Factory size={17}/></span><span><strong>{site.name}</strong><small>{site.code}</small></span><ChevronRight size={15}/></button>) : <div className="list-empty">No sites created yet.</div>}</div>
      </section>
      <section className="panel config-panel"><div className="panel-header"><div><div className="panel-kicker">STEP 02</div><h2>Assembly stations</h2></div><div className="panel-icon"><SlidersHorizontal size={18}/></div></div>
        <form className="stack-form" onSubmit={createStation}><label htmlFor="station-site">Parent site</label><select id="station-site" required value={selectedSite} onChange={(e) => setSelectedSite(e.target.value)}><option value="">Select a site</option>{sites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select><label htmlFor="station-name">Station name</label><input id="station-name" required maxLength={160} value={stationName} onChange={(e) => setStationName(e.target.value)}/><label htmlFor="station-code">Station code</label><input id="station-code" required maxLength={64} pattern="[A-Za-z0-9_-]+" value={stationCode} onChange={(e) => setStationCode(e.target.value)}/><button className="button button-secondary full-width" type="submit" disabled={!canConfigure || saving || !selectedSite}><Plus size={16}/> Create station</button></form>
        <div className="config-list-label">STATIONS IN SELECTED SITE <span>{displayedStations.length}</span></div><div className="simple-list">{displayedStations.length ? displayedStations.map((station) => <button key={station.id} className={`simple-list-item ${selectedStation === station.id ? "simple-list-active" : ""}`} onClick={() => setSelectedStation(station.id)}><span className="simple-list-icon"><SlidersHorizontal size={17}/></span><span><strong>{station.name}</strong><small>{station.code} · {station.is_active ? "Active" : "Inactive"}</small></span><ChevronRight size={15}/></button>) : <div className="list-empty">No station in this site yet.</div>}</div>
      </section>
    </div>
    <section className="panel rule-config-panel"><div className="panel-header"><div><div className="panel-kicker">STEP 03</div><h2>Inspection rule builder</h2><p className="panel-description">Define automated visual inspection criteria and region boundaries for this station.</p></div><div className="panel-icon"><Save size={18}/></div></div>
      <div className="rule-builder-grid"><form className="stack-form" onSubmit={createRule}><label htmlFor="rule-station">Target station</label><select id="rule-station" value={selectedStation} onChange={(e) => setSelectedStation(e.target.value)} required><option value="">Select a station</option>{stations.map((s) => <option key={s.id} value={s.id}>{s.name} · {s.code}</option>)}</select><label htmlFor="rule-name">Rule name</label><input id="rule-name" value={ruleName} onChange={(e) => setRuleName(e.target.value)} required maxLength={160}/><label htmlFor="rule-type">Rule type</label><select id="rule-type" value={ruleType} onChange={(e) => { setRuleType(e.target.value); setRuleConfig(e.target.value === "motion_stall" ? defaultMotionConfig : e.target.value === "surface_defect" ? defaultSurfaceConfig : e.target.value === "object_detection" ? defaultObjectConfig : defaultColorConfig); }}><option value="color_presence">Color presence / missing component heuristic</option><option value="motion_stall">Motion stall heuristic</option><option value="surface_defect">Scratch / crack candidate heuristic</option><option value="object_detection">YOLO object / defect detection (CPU)</option></select><label htmlFor="rule-severity">Event severity</label><select id="rule-severity" value={severity} onChange={(e) => setSeverity(e.target.value)}><option value="info">Informational</option><option value="warning">Warning</option><option value="high">High</option><option value="critical">Critical</option></select>
{["color_presence", "surface_defect"].includes(ruleType) && <VisualZoneDrawer ruleType={ruleType} configJson={ruleConfig} onChange={(updated) => setRuleConfig(updated)} />}
<label htmlFor="rule-config">Rule configuration (JSON)</label><textarea id="rule-config" className="json-editor" rows={11} spellCheck={false} value={ruleConfig} onChange={(e) => setRuleConfig(e.target.value)}/><button type="submit" className="button button-primary full-width" disabled={!canConfigure || saving || !selectedStation}>{saving ? "Saving…" : "Save inspection rule"} <ArrowRight size={16}/></button></form>
        <div className="rule-explainer"><div className="rule-explainer-card"><div className="rule-explainer-icon"><CircleHelp size={20}/></div><strong>{ruleType === "color_presence" ? "Color-presence rule" : ruleType === "motion_stall" ? "Motion-stall rule" : ruleType === "surface_defect" ? "Surface anomaly heuristic" : "YOLO detector rule"}</strong><p>{ruleType === "color_presence" ? "Checks a normalized image region for pixels matching an HSV color range. If the color stays below the minimum ratio for multiple sampled frames, it creates a potential missing-component event." : ruleType === "motion_stall" ? "Compares sampled frames and raises a possible inactivity event when mean frame difference stays below a configured threshold for long enough." : ruleType === "surface_defect" ? "Uses CPU OpenCV morphology and background suppression to rank elongated scratch/crack-like image regions. Scores are heuristic priorities, not calibrated probabilities." : "Runs a separately supplied YOLO weight file through Ultralytics on CPU. Add model_path or set YOLO_MODEL_PATH; weights are not bundled."}</p></div><div className="rule-field-help"><strong>{ruleType === "surface_defect" ? "Surface heuristic fields" : ruleType === "object_detection" ? "YOLO rule fields" : "Color rule fields"}</strong><code>{ruleType === "surface_defect" ? "threshold / min_area / min_aspect_ratio" : ruleType === "object_detection" ? "model_path / target_classes / confidence" : "zone"}</code><span>{ruleType === "surface_defect" ? "Tune candidate sensitivity on good and defective examples under fixed lighting; review evidence manually." : ruleType === "object_detection" ? "Provide a trained model file and class labels matching your dataset. The inference path is CPU-only." : "Normalized [x1, y1, x2, y2] coordinates from 0 to 1."}</span>{ruleType !== "surface_defect" && ruleType !== "object_detection" && <><code>zone</code><span>Normalized [x1, y1, x2, y2] coordinates from 0 to 1.</span><code>hsv_lower / hsv_upper</code><span>HSV color-range bounds in OpenCV scale.</span><code>min_pixel_ratio</code><span>Minimum fraction of ROI pixels that match the chosen color.</span><code>min_consecutive</code><span>Sampled low-presence observations required before alerting.</span></>}</div></div>
      </div>
      <div className="config-list-label existing-rules-heading">EXISTING RULES FOR SELECTED STATION <span>{selectedStationRules.length}</span></div><div className="rule-cards">{selectedStationRules.length ? selectedStationRules.map((rule) => <div key={rule.id} className="rule-card"><div className="rule-card-icon"><SlidersHorizontal size={17}/></div><div className="rule-card-main"><strong>{rule.name}</strong><span>{prettyLabel(rule.rule_type)} · Version {rule.version}</span><code>{JSON.stringify(rule.config)}</code></div><div className="rule-card-status"><span className={`severity-tag severity-tag-${rule.severity}`}>{prettyLabel(rule.severity)}</span><span className={`tiny-state ${rule.is_enabled ? "tiny-state-on" : ""}`}>{rule.is_enabled ? "Enabled" : "Disabled"}</span></div></div>) : <div className="list-empty rule-empty">No inspection rules configured for this station.</div>}</div>
    </section>
  </div>;
}
