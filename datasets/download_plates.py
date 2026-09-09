"""M2 dataset fetcher — download an Indian license-plate dataset in YOLOv8
format from Roboflow Universe, ready to train the plate detector (plate_yolo.pt).

WHY THIS EXISTS
  M2 needs labeled plate images to (a) train a YOLOv8 model that finds the plate
  region inside a vehicle crop, and (b) measure OCR accuracy on a held-out set.
  Roboflow exports images + YOLO labels + a data.yaml in one download.

ONE-TIME SETUP
  1. pip install roboflow            (added to requirements-dev below)
  2. Make a free account at https://roboflow.com
  3. Get your API key: https://app.roboflow.com  → Settings → API Key
  4. Pick a dataset on https://universe.roboflow.com (search "indian number plate"
     or "license plate"). Open it → Download → YOLOv8 → copy the workspace,
     project, and version from the code snippet it shows.

USAGE
  export ROBOFLOW_API_KEY=xxxxxxxxxxxx
  python -m datasets.download_plates \
      --workspace <workspace-slug> \
      --project   <project-slug> \
      --version   <n>

  # or pass the key inline:
  python -m datasets.download_plates --api-key xxxx --workspace ... --project ... --version 1

RESULT
  datasets/plates/               downloaded dataset (train/valid/test + data.yaml)
  datasets/plates/data.yaml      path you feed to `yolo detect train data=...`

Then M2 trains:
  yolo detect train data=datasets/plates/data.yaml model=yolov8n.pt epochs=80 imgsz=640
  cp runs/detect/train/weights/best.pt plate_yolo.pt
"""
import argparse
import os
import sys
from pathlib import Path

DEST = Path(__file__).resolve().parent / "plates"


def main():
    ap = argparse.ArgumentParser(description="Download a Roboflow plate dataset (YOLOv8).")
    ap.add_argument("--api-key", default=os.getenv("ROBOFLOW_API_KEY"),
                    help="Roboflow API key (or set ROBOFLOW_API_KEY env var).")
    ap.add_argument("--workspace", required=True, help="Roboflow workspace slug.")
    ap.add_argument("--project", required=True, help="Roboflow project slug.")
    ap.add_argument("--version", type=int, required=True, help="Dataset version number.")
    ap.add_argument("--format", default="yolov8", help="Export format (default yolov8).")
    args = ap.parse_args()

    if not args.api_key:
        sys.exit("ERROR: no API key. Set ROBOFLOW_API_KEY or pass --api-key. "
                 "Get one at https://app.roboflow.com → Settings → API Key.")

    try:
        from roboflow import Roboflow
    except ImportError:
        sys.exit("ERROR: roboflow not installed. Run:  pip install roboflow")

    DEST.mkdir(parents=True, exist_ok=True)
    # Roboflow downloads into a folder named <project>-<version> in cwd; we point
    # location at datasets/plates so training paths are stable.
    print(f"Downloading {args.workspace}/{args.project} v{args.version} ({args.format})...")
    rf = Roboflow(api_key=args.api_key)
    project = rf.workspace(args.workspace).project(args.project)
    dataset = project.version(args.version).download(args.format, location=str(DEST))

    data_yaml = Path(dataset.location) / "data.yaml"
    print("\nDone.")
    print(f"  dataset:   {dataset.location}")
    print(f"  data.yaml: {data_yaml}")
    print("\nTrain the plate detector:")
    print(f"  yolo detect train data={data_yaml} model=yolov8n.pt epochs=80 imgsz=640")
    print("  cp runs/detect/train/weights/best.pt plate_yolo.pt")


if __name__ == "__main__":
    main()
