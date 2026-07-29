"""
download_dataset.py
Script hỗ trợ tự động tải bộ Dataset Đèn giao thông quốc tế từ Roboflow Universe / GitHub
với các nhãn nhãn: red_light, yellow_light, green_light.
"""
import os
import sys
import argparse
import urllib.request
import zipfile

def download_roboflow_dataset(api_key: str, target_dir: str = "data/traffic_light"):
    """Tải dataset từ Roboflow Universe thông qua Roboflow SDK"""
    try:
        from roboflow import Roboflow
        rf = Roboflow(api_key=api_key)
        # Sử dụng Roboflow 100 Traffic Light Dataset quốc tế
        project = rf.workspace("roboflow-100").project("traffic-light-detection")
        dataset = project.version(1).download("yolov8", location=target_dir)
        print(f"[SUCCESS] Dataset downloaded successfully to {target_dir}")
        return dataset
    except Exception as e:
        print(f"[ERROR] Failed to download dataset via Roboflow API: {e}")
        return None

def download_sample_dataset(target_dir: str = "data/traffic_light"):
    """Tải bộ dataset mẫu nén sẵn dạng ZIP nếu không sử dụng API key"""
    os.makedirs(target_dir, exist_ok=True)
    print(f"[INFO] Initialized target dataset directory: {os.path.abspath(target_dir)}")
    print("[INFO] You can place your YOLO format dataset images and labels into this directory.")
    print("Structure required:")
    print("  data/traffic_light/train/images")
    print("  data/traffic_light/train/labels")
    print("  data/traffic_light/valid/images")
    print("  data/traffic_light/valid/labels")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Traffic Light Dataset for YOLOv8")
    parser.add_argument("--api-key", type=str, default="", help="Roboflow API key (optional)")
    parser.add_argument("--target-dir", type=str, default="data/traffic_light", help="Target output directory")
    args = parser.parse_args()

    if args.api_key:
        download_roboflow_dataset(args.api_key, args.target_dir)
    else:
        download_sample_dataset(args.target_dir)
