"""M1 visual check: watch tracked boxes + IDs on a video window.

Usage:
    python -m datasets.preview datasets/sample.mp4
    python -m datasets.preview datasets/sample.mp4 yolov8s.pt

Press 'q' to quit. This is a DIAGNOSTIC tool — the real code lives in
vision/vehicle_tracker.py. Use it to confirm track IDs stay glued to each
vehicle (the thing M2's plate voting depends on).

It uses the same YOLO model + ByteTrack config as VehicleTracker, and uses
Ultralytics' built-in .plot() to draw labeled, ID-tagged boxes on each frame.
"""
import sys
import cv2
from ultralytics import YOLO

from vision.vehicle_tracker import VEHICLE_CLASSES


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python -m datasets.preview <video_or_rtsp> [model.pt]")
    source = sys.argv[1]
    model_path = sys.argv[2] if len(sys.argv) > 2 else "yolov8s.pt"

    model = YOLO(model_path)
    for res in model.track(
        source=source, stream=True, tracker="bytetrack.yaml",
        classes=list(VEHICLE_CLASSES), verbose=False,
    ):
        frame = res.plot()  # draws boxes, class labels, and track IDs
        cv2.imshow("M1 tracking preview — press q to quit", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
