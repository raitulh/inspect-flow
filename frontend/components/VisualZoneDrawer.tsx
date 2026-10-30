"use client";

import { useCallback, useEffect, useRef, useState, MouseEvent } from "react";
import { Crosshair, Sparkles } from "lucide-react";

const PRESETS: { label: string; zone: [number, number, number, number] }[] = [
  { label: "Full Frame", zone: [0.0, 0.0, 1.0, 1.0] },
  { label: "Center 80%", zone: [0.1, 0.1, 0.9, 0.9] },
  { label: "Center 50%", zone: [0.25, 0.25, 0.75, 0.75] },
  { label: "Top Half", zone: [0.0, 0.0, 1.0, 0.5] },
  { label: "Bottom Half", zone: [0.0, 0.5, 1.0, 1.0] },
  { label: "Left Half", zone: [0.0, 0.0, 0.5, 1.0] },
  { label: "Right Half", zone: [0.5, 0.0, 1.0, 1.0] },
];

export default function VisualZoneDrawer({ configJson, onChange }: { ruleType?: string; configJson: string; onChange: (updatedJson: string) => void }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);
  const [activeZone, setActiveZone] = useState<[number, number, number, number]>([0.15, 0.15, 0.85, 0.85]);
  const [adaptiveLighting, setAdaptiveLighting] = useState<boolean>(false);

  // Parse current zone and adaptive lighting from configJson
  useEffect(() => {
    try {
      const parsed = JSON.parse(configJson) as Record<string, unknown>;
      if (Array.isArray(parsed.zone) && parsed.zone.length === 4) {
        setActiveZone(parsed.zone as [number, number, number, number]);
      }
      setAdaptiveLighting(Boolean(parsed.adaptive_lighting));
    } catch {
      // Keep current state on invalid JSON
    }
  }, [configJson]);

  const updateConfig = useCallback(
    (newZone: [number, number, number, number], newAdaptive: boolean) => {
      try {
        const parsed = (JSON.parse(configJson || "{}") as Record<string, unknown>) || {};
        parsed.zone = newZone;
        if (newAdaptive) {
          parsed.adaptive_lighting = true;
        } else {
          delete parsed.adaptive_lighting;
        }
        onChange(JSON.stringify(parsed, null, 2));
      } catch {
        // Fallback to minimal JSON
        onChange(JSON.stringify({ zone: newZone, adaptive_lighting: newAdaptive }, null, 2));
      }
    },
    [configJson, onChange]
  );

  // Redraw canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Background gradient - simulated camera feed / industrial inspection plate
    const bgGrad = ctx.createLinearGradient(0, 0, width, height);
    bgGrad.addColorStop(0, "#232b28");
    bgGrad.addColorStop(1, "#181f1d");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);

    // Subtle inspection grid
    ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
    ctx.lineWidth = 1;
    for (let x = 20; x < width; x += 20) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 20; y < height; y += 20) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Assembly station center crosshair
    ctx.strokeStyle = "rgba(197, 139, 97, 0.25)";
    ctx.beginPath();
    ctx.moveTo(width / 2 - 12, height / 2);
    ctx.lineTo(width / 2 + 12, height / 2);
    ctx.moveTo(width / 2, height / 2 - 12);
    ctx.lineTo(width / 2, height / 2 + 12);
    ctx.stroke();

    // Draw active zone
    const [x1, y1, x2, y2] = activeZone;
    const rx = Math.round(x1 * width);
    const ry = Math.round(y1 * height);
    const rw = Math.round((x2 - x1) * width);
    const rh = Math.round((y2 - y1) * height);

    // Zone highlight fill
    ctx.fillStyle = "rgba(165, 106, 69, 0.16)";
    ctx.fillRect(rx, ry, rw, rh);

    // Zone bounding stroke
    ctx.strokeStyle = "#c58b61";
    ctx.lineWidth = 2;
    ctx.strokeRect(rx, ry, rw, rh);

    // Corner anchor points
    ctx.fillStyle = "#f6f0e6";
    const cornerSize = 4;
    ctx.fillRect(rx - cornerSize / 2, ry - cornerSize / 2, cornerSize, cornerSize);
    ctx.fillRect(rx + rw - cornerSize / 2, ry - cornerSize / 2, cornerSize, cornerSize);
    ctx.fillRect(rx - cornerSize / 2, ry + rh - cornerSize / 2, cornerSize, cornerSize);
    ctx.fillRect(rx + rw - cornerSize / 2, ry + rh - cornerSize / 2, cornerSize, cornerSize);

    // Text badge on the box
    ctx.fillStyle = "rgba(0, 0, 0, 0.75)";
    ctx.fillRect(rx + 4, ry + 4, 110, 18);
    ctx.fillStyle = "#e3e8e0";
    ctx.font = "9px 'DM Mono', monospace";
    ctx.fillText(`ZONE [${x1.toFixed(2)}, ${y1.toFixed(2)}]`, rx + 8, ry + 16);
  }, [activeZone]);

  const handleMouseDown = (e: MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
    setIsDrawing(true);
    setStartPoint({ x, y });
  };

  const handleMouseMove = (e: MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !startPoint || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const currentX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const currentY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));

    const x1 = parseFloat(Math.min(startPoint.x, currentX).toFixed(3));
    const y1 = parseFloat(Math.min(startPoint.y, currentY).toFixed(3));
    const x2 = parseFloat(Math.max(startPoint.x, currentX).toFixed(3));
    const y2 = parseFloat(Math.max(startPoint.y, currentY).toFixed(3));

    if (x2 - x1 > 0.02 && y2 - y1 > 0.02) {
      setActiveZone([x1, y1, x2, y2]);
    }
  };

  const handleMouseUp = () => {
    if (isDrawing) {
      setIsDrawing(false);
      setStartPoint(null);
      updateConfig(activeZone, adaptiveLighting);
    }
  };

  const applyPreset = (presetZone: [number, number, number, number]) => {
    setActiveZone(presetZone);
    updateConfig(presetZone, adaptiveLighting);
  };

  const toggleAdaptive = () => {
    const next = !adaptiveLighting;
    setAdaptiveLighting(next);
    updateConfig(activeZone, next);
  };

  const coveragePercent = Math.round((activeZone[2] - activeZone[0]) * (activeZone[3] - activeZone[1]) * 100);

  return (
    <div
      style={{
        marginTop: "10px",
        marginBottom: "12px",
        background: "rgba(0, 0, 0, 0.18)",
        border: "1px solid #414a45",
        borderRadius: "9px",
        padding: "12px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "8px",
        }}
      >
        <span
          style={{
            fontSize: "10px",
            fontWeight: 700,
            letterSpacing: "1px",
            color: "#c58b61",
            display: "flex",
            alignItems: "center",
            gap: "5px",
          }}
        >
          <Crosshair size={13} /> VISUAL ROI ZONE PICKER
        </span>
        <span style={{ fontSize: "9px", color: "#8a968e", fontFamily: "monospace" }}>
          Coverage: {coveragePercent}% · [{activeZone.map((n) => n.toFixed(2)).join(", ")}]
        </span>
      </div>

      {/* Interactive Canvas */}
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "170px",
          borderRadius: "7px",
          overflow: "hidden",
          cursor: "crosshair",
          border: "1px solid rgba(255, 255, 255, 0.08)",
        }}
      >
        <canvas
          ref={canvasRef}
          width={400}
          height={170}
          style={{ width: "100%", height: "100%", display: "block" }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        />
        <div
          style={{
            position: "absolute",
            bottom: "6px",
            left: "8px",
            fontSize: "8.5px",
            color: "#839087",
            pointerEvents: "none",
            background: "rgba(0,0,0,0.6)",
            padding: "2px 6px",
            borderRadius: "4px",
          }}
        >
          Drag with mouse on canvas to define custom ROI coordinates
        </div>
      </div>

      {/* Preset Buttons */}
      <div style={{ marginTop: "8px", display: "flex", gap: "5px", flexWrap: "wrap" }}>
        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            className="button button-secondary"
            style={{
              minHeight: "24px",
              padding: "0 7px",
              fontSize: "8.5px",
              borderRadius: "5px",
              background:
                activeZone.every((v, i) => Math.abs(v - p.zone[i]) < 0.01)
                  ? "rgba(165, 106, 69, 0.28)"
                  : "#2d3532",
              borderColor:
                activeZone.every((v, i) => Math.abs(v - p.zone[i]) < 0.01) ? "#c58b61" : "#414a45",
            }}
            onClick={() => applyPreset(p.zone)}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Lighting Normalization Switch */}
      <div
        style={{
          marginTop: "10px",
          paddingTop: "8px",
          borderTop: "1px solid rgba(255, 255, 255, 0.05)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: "7px",
            fontSize: "10px",
            color: "#d0d8d0",
            cursor: "pointer",
            margin: 0,
          }}
        >
          <input
            type="checkbox"
            checked={adaptiveLighting}
            onChange={toggleAdaptive}
            style={{ accentColor: "#c58b61", cursor: "pointer" }}
          />
          <Sparkles size={13} style={{ color: "#c58b61" }} />
          <span>Adaptive lighting normalization (CLAHE)</span>
        </label>
        <span style={{ fontSize: "8.5px", color: "#87938a" }}>Stabilizes shadow & glare</span>
      </div>
    </div>
  );
}
