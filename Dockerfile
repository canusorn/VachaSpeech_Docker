FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    libsndfile1 \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --upgrade pip

RUN pip install --timeout 300 --retries 10 \
    torch \
    torchaudio \
    flask \
    flask-cors \
    --extra-index-url https://download.pytorch.org/whl/cu121

RUN pip install accelerate transformers && \
    pip install git+https://github.com/VYNCX/VachaSpeech.git

COPY app.py .

EXPOSE 7860

CMD ["python", "app.py"]