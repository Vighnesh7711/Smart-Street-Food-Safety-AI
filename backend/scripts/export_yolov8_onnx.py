"""Export a YOLO-family detector to ONNX for the hygiene CV pipeline.

RUN THIS IN A THROWAWAY ENVIRONMENT, NOT THE BACKEND VENV
---------------------------------------------------------
This script needs `ultralytics`, which pulls ~2.5 GB of torch plus the
non-headless `opencv-python` build. The backend deliberately does not install
it: `onnxruntime` runs the exported graph in ~50 MB, with no torch, and
without a second copy of OpenCV fighting over the `cv2` package.

So the workflow is:

    # In a SEPARATE venv or a Colab notebook -- once.
    pip install ultralytics
    python backend/scripts/export_yolov8_onnx.py

    # Then, in the backend venv, nothing to install. Just point at it:
    #   backend/.env
    CV_PROVIDER=onnx_yolo
    CV_MODEL_PATH=var/models/yolov8n.onnx

The backend never downloads model weights itself. Silently fetching an
unverified binary into a service that reports on people's livelihoods is not
a trade worth making for convenience -- so the weights come from a command
you ran and can inspect.

WHAT YOU GET, AND WHAT IT IS NOT
--------------------------------
`yolov8n` is pretrained on COCO. COCO's 80 classes contain **no hygiene
indicators**. It detects "cup", "bowl", "person", "dog" -- which
`hygiene_indicators.cv_labels` maps onto placeholder indicators so the
pipeline has real detections to score. It is a stand-in. Once you fine-tune
on real stall photos, re-run this script and update the `cv_labels` seed;
nothing else needs to change.

Usage:
    python export_yolov8_onnx.py [--model yolov8n.pt] [--size 640]
                                 [--output var/models/yolov8n.onnx]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

#: Backend root (this file lives in backend/scripts/).
BACKEND_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUTPUT = BACKEND_ROOT / "var" / "models" / "yolov8n.onnx"


def _fail(message: str, hint: str | None = None) -> int:
    print(f"\nERROR: {message}", file=sys.stderr)
    if hint:
        print(f"\n{hint}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a YOLO model to ONNX for the hygiene CV pipeline."
    )
    parser.add_argument(
        "--model",
        default="yolov8n.pt",
        help="Ultralytics model name or path. Use your fine-tuned weights here.",
    )
    parser.add_argument(
        "--size", type=int, default=640, help="Input image size (default 640)."
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Where to write the .onnx file (default backend/var/models/yolov8n.onnx).",
    )
    parser.add_argument(
        "--opset", type=int, default=12, help="ONNX opset version (default 12)."
    )
    args = parser.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError:
        return _fail(
            "ultralytics is not installed in this environment.",
            "This is expected if you are running inside the backend venv.\n"
            "Create a separate environment for the export:\n\n"
            "    python -m venv .venv-export\n"
            "    .venv-export/Scripts/pip install ultralytics   # Windows\n"
            "    .venv-export/bin/pip install ultralytics       # macOS/Linux\n"
            "    .venv-export/Scripts/python export_yolov8_onnx.py\n\n"
            "Then delete the export environment. The backend only needs the "
            ".onnx file.",
        )

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (BACKEND_ROOT / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading {args.model} (weights download on first run)...")
    try:
        model = YOLO(args.model)
    except Exception as exc:  # noqa: BLE001 - ultralytics raises broadly
        return _fail(
            f"Could not load {args.model!r}: {exc}",
            "If this is a network failure, download the weights manually and "
            "pass a local path with --model.",
        )

    print(f"Exporting to ONNX (imgsz={args.size}, opset={args.opset})...")
    try:
        exported = model.export(
            format="onnx",
            imgsz=args.size,
            opset=args.opset,
            simplify=True,
            dynamic=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"Export failed: {exc}")

    exported_path = Path(exported)
    if not exported_path.exists():
        return _fail(f"Export reported success but {exported_path} does not exist.")

    if exported_path.resolve() != output_path:
        shutil.move(str(exported_path), str(output_path))

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nWrote {output_path} ({size_mb:.1f} MB)")
    print(
        "\nNext steps:\n"
        f"  1. Set CV_MODEL_PATH={output_path} in backend/.env\n"
        "     (a relative path resolves against backend/)\n"
        "  2. Set CV_PROVIDER=onnx_yolo in backend/.env\n"
        "  3. Verify:  python -m pytest tests/test_cv_onnx.py -q\n"
        "\nRemember: until this model is fine-tuned on stall photos, its "
        "output is a\nplaceholder. See the note at the top of this file."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
