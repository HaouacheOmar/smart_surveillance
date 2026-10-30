import os
import threading
from functools import lru_cache

import torch
from deep_sort_realtime.deepsort_tracker import DeepSort
from ultralytics import YOLO

if torch.cuda.is_available():
    # Heavy work runs on the GPU; per-thread CPU pools across camera threads only oversubscribe the cores.
    torch.set_num_threads(1)

# ponytail: one shared model behind a global lock; batch frames across cameras (or one model per GPU) past ~10 cams
inference_lock = threading.Lock()


@lru_cache(maxsize=1)
def load_pose_model():
    return YOLO(os.environ.get("POSE_MODEL", "yolo26n-pose.pt"))


def new_tracker():
    """One DeepSORT instance per camera: n_init frames before a person is counted, max_age before dropped."""
    return DeepSort(max_age=15, n_init=3, embedder="mobilenet", embedder_gpu=torch.cuda.is_available())
