# FastAPI vision service (YOLO26-pose + DeepSORT). Build context: repository root.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# One thread per native math pool: work is on the GPU, and per-core OpenBLAS/OpenMP pools spin-wait
# between DeepSORT's many small numpy calls, burning ~7 cores and starving the camera threads.
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# CUDA 13.0 wheels (bundle the CUDA runtime; the host only needs the NVIDIA driver).
# CPU-only host: --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cpu
ARG TORCH_INDEX=https://download.pytorch.org/whl/cu130
RUN pip install --no-cache-dir torch torchvision --index-url ${TORCH_INDEX}
COPY vision_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "from ultralytics import YOLO; YOLO('yolo26n-pose.pt')"
COPY vision_service/*.py ./
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
