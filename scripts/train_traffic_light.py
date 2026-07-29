"""
train_traffic_light.py
Script huấn luyện model YOLOv8 cho nhận diện Đèn giao thông và phân loại trạng thái (Đỏ, Vàng, Xanh).
"""
import os
import sys
import argparse

def train_model(data_yaml: str, base_model: str = "yolov8n.pt", epochs: int = 50, imgsz: int = 640, output_dir: str = "models"):
    """Thực thi huấn luyện YOLOv8 qua Ultralytics Python API"""
    try:
        from ultralytics import YOLO
        
        print(f"[INFO] Initializing base model: {base_model}")
        model = YOLO(base_model)
        
        print(f"[INFO] Starting training with data config: {data_yaml}, epochs={epochs}, imgsz={imgsz}")
        results = model.train(
            data=data_yaml,
            epochs=epochs,
            imgsz=imgsz,
            batch=16,
            name="traffic_light_run",
            exist_ok=True
        )
        
        os.makedirs(output_dir, exist_ok=True)
        trained_weights_path = os.path.join("runs", "detect", "traffic_light_run", "weights", "best.pt")
        target_model_path = os.path.join(output_dir, "traffic_light.pt")
        
        if os.path.exists(trained_weights_path):
            import shutil
            shutil.copy(trained_weights_path, target_model_path)
            print(f"[SUCCESS] Trained model weights saved to {target_model_path}")
        else:
            print(f"[WARNING] Could not locate best weights at {trained_weights_path}. Saving current model export.")
            model.export(format="pt")
            
        return results
    except Exception as e:
        print(f"[ERROR] Training failed: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train YOLOv8 Traffic Light Detection Model")
    parser.add_argument("--data", type=str, default="data/data_traffic_light.yaml", help="Path to data yaml config")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="Base model checkpoint")
    parser.add_argument("--epochs", type=int, default=50, help="Number of epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size for inference/training")
    parser.add_argument("--output-dir", type=str, default="models", help="Output directory for final .pt file")
    
    args = parser.parse_args()
    train_model(args.data, args.model, args.epochs, args.imgsz, args.output_dir)
