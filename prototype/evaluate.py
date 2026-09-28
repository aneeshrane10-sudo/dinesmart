"""
evaluate.py — Batch evaluation of YOLOv8 on the Roboflow dataset
"""

import os
from pathlib import Path
from ultralytics import YOLO

def main():
    dataset_yaml = Path(__file__).parent / "dataset" / "data.yaml"
    model_path = Path(__file__).parent / "yolov8n.pt"

    print("=" * 60)
    print("DineSmart — YOLOv8 Model Batch Evaluation")
    print(f"Model:   {model_path}")
    print(f"Dataset: {dataset_yaml}")
    print("=" * 60)

    model = YOLO(str(model_path))

    # Evaluate on Validation Split
    print("\n--- Evaluating on Validation Set (val) ---")
    val_results = model.val(
        data=str(dataset_yaml),
        split="val",
        batch=1,
        conf=0.25,
        iou=0.6,
        plots=False,
        save_json=False,
        verbose=True,
    )

    print("\n[Validation Metrics Summary]")
    print(f"  Precision (P)    : {val_results.results_dict.get('metrics/precision(B)', 0.0):.4f}")
    print(f"  Recall (R)       : {val_results.results_dict.get('metrics/recall(B)', 0.0):.4f}")
    print(f"  mAP50            : {val_results.results_dict.get('metrics/mAP50(B)', 0.0):.4f}")
    print(f"  mAP50-95         : {val_results.results_dict.get('metrics/mAP50-95(B)', 0.0):.4f}")
    print(f"  Speed (preprocess/inference/postprocess): "
          f"{val_results.speed['preprocess']:.2f}ms / "
          f"{val_results.speed['inference']:.2f}ms / "
          f"{val_results.speed['postprocess']:.2f}ms per image")

    # Evaluate on Test Split
    print("\n--- Evaluating on Test Set (test) ---")
    test_results = model.val(
        data=str(dataset_yaml),
        split="test",
        batch=1,
        conf=0.25,
        iou=0.6,
        plots=False,
        save_json=False,
        verbose=True,
    )

    print("\n[Test Metrics Summary]")
    print(f"  Precision (P)    : {test_results.results_dict.get('metrics/precision(B)', 0.0):.4f}")
    print(f"  Recall (R)       : {test_results.results_dict.get('metrics/recall(B)', 0.0):.4f}")
    print(f"  mAP50            : {test_results.results_dict.get('metrics/mAP50(B)', 0.0):.4f}")
    print(f"  mAP50-95         : {test_results.results_dict.get('metrics/mAP50-95(B)', 0.0):.4f}")
    print(f"  Speed (preprocess/inference/postprocess): "
          f"{test_results.speed['preprocess']:.2f}ms / "
          f"{test_results.speed['inference']:.2f}ms / "
          f"{test_results.speed['postprocess']:.2f}ms per image")

if __name__ == "__main__":
    main()
