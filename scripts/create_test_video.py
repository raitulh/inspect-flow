"""Generate a realistic factory conveyor inspection test video for LineGuard CV.

Simulates an industrial conveyor belt with passing workpieces:
- Item 1: Perfect golden sample (Passes all checks)
- Item 2: Defective workpiece with severe surface crack / scratch (Triggers surface_defect rule)
- Item 3: Defective workpiece with missing component / cap (Triggers color_presence / missing component rule)
- Item 4: Normal sample passing through
"""

from __future__ import annotations

import argparse
from pathlib import Path
import cv2
import numpy as np


def draw_conveyor_background(frame: np.ndarray, offset: int) -> None:
    h, w = frame.shape[:2]
    # Factory floor background (dark slate gray)
    frame[:] = (35, 38, 42)

    # Conveyor belt rails (steel borders)
    cv2.rectangle(frame, (0, 70), (w, 290), (55, 60, 65), -1)  # belt frame
    cv2.rectangle(frame, (0, 85), (w, 275), (28, 30, 32), -1)  # moving black rubber belt

    # Conveyor side guards
    cv2.line(frame, (0, 84), (w, 84), (110, 115, 120), 2)
    cv2.line(frame, (0, 276), (w, 276), (110, 115, 120), 2)

    # Conveyor belt texture slats (moving lines)
    step = 40
    for x in range((offset % step) - step, w + step, step):
        cv2.line(frame, (x, 86), (x, 274), (38, 42, 45), 1)

    # Factory overhead lighting reflection strip
    cv2.line(frame, (0, 95), (w, 95), (45, 48, 52), 1)


def draw_hud(frame: np.ndarray, frame_num: int, total_frames: int, active_item_text: str) -> None:
    h, w = frame.shape[:2]
    # Header bar
    cv2.rectangle(frame, (0, 0), (w, 36), (20, 24, 28), -1)
    cv2.line(frame, (0, 36), (w, 36), (50, 58, 65), 1)

    # Status indicators
    cv2.circle(frame, (18, 18), 5, (0, 220, 100), -1)  # Green live status
    cv2.putText(frame, "CAM-01 [INSPECTION LINE 1]", (32, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 225, 230), 1, cv2.LINE_AA)
    
    fps_text = f"FRAME: {frame_num:03d}/{total_frames}  |  CONVEYOR: 0.42 m/s"
    cv2.putText(frame, fps_text, (w - 290, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (160, 175, 185), 1, cv2.LINE_AA)

    # Bottom status bar showing item being scanned
    cv2.rectangle(frame, (0, h - 30), (w, h), (20, 24, 28), -1)
    cv2.line(frame, (0, h - 30), (w, h - 30), (50, 58, 65), 1)
    cv2.putText(frame, f"TARGET: {active_item_text}", (16, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 210, 255), 1, cv2.LINE_AA)

    # Calibration crosshairs / ROI indicator guidelines in the inspection zone (center)
    roi_x1, roi_y1, roi_x2, roi_y2 = 220, 90, 420, 270
    cv2.rectangle(frame, (roi_x1, roi_y1), (roi_x2, roi_y2), (70, 80, 90), 1)
    cv2.putText(frame, "PRIMARY INSPECTION ZONE", (roi_x1 + 6, roi_y1 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (100, 120, 135), 1, cv2.LINE_AA)


def draw_workpiece(frame: np.ndarray, center_x: int, center_y: int, workpiece_type: str) -> None:
    """Draw an industrial machined casing workpiece with components or defects."""
    w, h = 130, 110
    x1 = center_x - w // 2
    y1 = center_y - h // 2
    x2 = x1 + w
    y2 = y1 + h

    # Outer drop shadow
    cv2.rectangle(frame, (x1 + 4, y1 + 4), (x2 + 4, y2 + 4), (18, 20, 22), -1)

    # Main metal chassis (beveled rectangle)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (170, 175, 180), -1)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (210, 215, 220), 2)  # Outer highlight
    cv2.rectangle(frame, (x1 + 6, y1 + 6), (x2 - 6, y2 - 6), (145, 150, 155), -1)  # Recessed tray

    # Corner mounting screws
    screw_color = (80, 85, 90)
    for sx, sy in [(x1 + 12, y1 + 12), (x2 - 12, y1 + 12), (x1 + 12, y2 - 12), (x2 - 12, y2 - 12)]:
        cv2.circle(frame, (sx, sy), 4, screw_color, -1)
        cv2.line(frame, (sx - 2, sy), (sx + 2, sy), (180, 185, 190), 1)

    # Center Component Socket
    socket_x1, socket_y1 = center_x - 30, center_y - 25
    socket_x2, socket_y2 = center_x + 30, center_y + 25
    cv2.rectangle(frame, (socket_x1, socket_y1), (socket_x2, socket_y2), (50, 52, 55), -1)

    # Workpiece condition specifics
    if workpiece_type == "normal":
        # Vibrant Blue-ish IC/Cap Component installed (RGB: 30, 80, 210 -> BGR: 210, 80, 30)
        cv2.rectangle(frame, (socket_x1 + 4, socket_y1 + 4), (socket_x2 - 4, socket_y2 - 4), (215, 85, 30), -1)
        cv2.rectangle(frame, (socket_x1 + 4, socket_y1 + 4), (socket_x2 - 4, socket_y2 - 4), (240, 130, 60), 1)
        # Small gold pin indicator
        cv2.circle(frame, (socket_x1 + 10, socket_y1 + 10), 2, (30, 200, 240), -1)

    elif workpiece_type == "missing_component":
        # Empty socket - component was skipped during assembly!
        # Just dark solder pads visible inside
        cv2.circle(frame, (socket_x1 + 12, center_y), 3, (80, 85, 90), -1)
        cv2.circle(frame, (socket_x2 - 12, center_y), 3, (80, 85, 90), -1)
        cv2.putText(frame, "EMPTY", (socket_x1 + 8, center_y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (90, 95, 100), 1, cv2.LINE_AA)

    elif workpiece_type == "surface_defect":
        # Normal component IS present
        cv2.rectangle(frame, (socket_x1 + 4, socket_y1 + 4), (socket_x2 - 4, socket_y2 - 4), (215, 85, 30), -1)
        # BUT there is a prominent high-contrast jagged scratch/crack on the metal face
        # Sharp jagged black-hat crack
        pts = np.array([
            [x1 + 18, y1 + 25],
            [x1 + 35, y1 + 40],
            [x1 + 48, y1 + 36],
            [x1 + 75, y1 + 68],
            [x1 + 92, y1 + 78],
            [x1 + 110, y1 + 92]
        ], np.int32)
        cv2.polylines(frame, [pts], False, (15, 15, 18), 3, cv2.LINE_AA)
        cv2.polylines(frame, [pts], False, (250, 250, 255), 1, cv2.LINE_AA)  # Highlight edge


def generate_video(output_mp4: Path, output_avi: Path, total_frames: int = 240, fps: float = 24.0) -> None:
    width, height = 640, 360
    
    # Try MP4 writer first
    mp4_writer = None
    try:
        mp4_writer = cv2.VideoWriter(str(output_mp4), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not mp4_writer.isOpened():
            mp4_writer = None
    except Exception:
        mp4_writer = None

    avi_writer = cv2.VideoWriter(str(output_avi), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height))
    if not avi_writer.isOpened():
        raise RuntimeError("OpenCV could not open MJPG VideoWriter")

    # We will simulate 3 products moving across the conveyor:
    # Product 1: Normal (enters frame 0, exits frame 90)
    # Product 2: Surface Defect Crack (enters frame 80, center frame 140, exits 200)
    # Product 3: Missing Component (enters frame 160, center frame 210, exits 270)
    
    speed_px_per_frame = 4.8  # conveyor velocity
    start_x = -70
    center_y = 180

    for f in range(total_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 1. Background conveyor motion
        conveyor_offset = int(f * speed_px_per_frame)
        draw_conveyor_background(frame, conveyor_offset)

        # Determine which items are currently on belt
        item_text = "CONVEYOR CLEAR"

        # Item 1: Normal
        item1_x = int(start_x + f * speed_px_per_frame)
        if -80 <= item1_x <= width + 80:
            draw_workpiece(frame, item1_x, center_y, "normal")
            if 180 <= item1_x <= 460:
                item_text = "UNIT #101: PASS (GOLDEN SPEC)"

        # Item 2: Surface Defect (Crack) - starts 320 px behind item 1
        item2_x = int(start_x - 320 + f * speed_px_per_frame)
        if -80 <= item2_x <= width + 80:
            draw_workpiece(frame, item2_x, center_y, "surface_defect")
            if 180 <= item2_x <= 460:
                item_text = "UNIT #102: ANOMALY (SURFACE FRACTURE)"

        # Item 3: Missing Component - starts 640 px behind item 1
        item3_x = int(start_x - 640 + f * speed_px_per_frame)
        if -80 <= item3_x <= width + 80:
            draw_workpiece(frame, item3_x, center_y, "missing_component")
            if 180 <= item3_x <= 460:
                item_text = "UNIT #103: ANOMALY (MISSING COMPONENT)"

        # 2. Draw HUD & Inspection Zone
        draw_hud(frame, f + 1, total_frames, item_text)

        # 3. Write frames
        if mp4_writer:
            mp4_writer.write(frame)
        avi_writer.write(frame)

    if mp4_writer:
        mp4_writer.release()
    avi_writer.release()

    print(f"Generated test videos successfully:")
    if output_mp4.exists():
        print(f" - MP4 (Browser & Player Ready): {output_mp4.resolve()} ({output_mp4.stat().st_size / 1024:.1f} KB)")
    if output_avi.exists():
        print(f" - AVI (OpenCV MJPG Ready):       {output_avi.resolve()} ({output_avi.stat().st_size / 1024:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mp4", type=Path, default=Path("conveyor_inspection_test.mp4"))
    parser.add_argument("--avi", type=Path, default=Path("conveyor_inspection_test.avi"))
    parser.add_argument("--frames", type=int, default=260)
    args = parser.parse_args()
    generate_video(args.mp4, args.avi, total_frames=args.frames)


if __name__ == "__main__":
    main()
