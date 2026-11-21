FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-pol && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py ./
COPY src ./src
COPY configs ./configs
COPY schemas ./schemas
COPY prompts ./prompts
COPY frontend ./frontend
RUN mkdir input output
CMD ["python", "main.py"]
