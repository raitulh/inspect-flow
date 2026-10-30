"""Generate an explicitly synthetic video for smoke-testing a color-presence rule."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("lineguard-synthetic-demo.avi"))
    parser.add_argument("--frames", type=int, default=120)
    args = parser.parse_args()
    if not 10 <= args.frames <= 5000:
        parser.error("--frames must be between 10 and 5000")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(args.output), cv2.VideoWriter_fourcc(*"MJPG"), 20.0, (640, 360))
    if not writer.isOpened():
        raise SystemExit("OpenCV could not initialize the MJPG video writer; check codec support.")
    absent_from = args.frames // 2
    for index in range(args.frames):
        frame = np.full((360, 640, 3), (50, 54, 52), dtype=np.uint8)
        cv2.rectangle(frame, (100, 60), (540, 310), (75, 81, 78), -1)
        cv2.rectangle(frame, (165, 120), (290, 245), (185, 105, 32), -1)  # orange equipment marker
        if index < absent_from:
            cv2.rectangle(frame, (360, 130), (450, 220), (220, 60, 20), -1)  # synthetic blue-ish component
        cv2.putText(frame, "SYNTHETIC TEST FOOTAGE - NOT A FACTORY RECORD", (16, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (245, 240, 230), 1, cv2.LINE_AA)
        writer.write(frame)
    writer.release()
    print(f"Created synthetic smoke-test video: {args.output.resolve()}")
    print("This fixture validates software workflow only; it is not evidence of industrial detection accuracy.")


if __name__ == "__main__":
    main()
