FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update -y && \
    apt-get install -y python3 python3-pip python3-dev libhdf5-dev python3-h5py && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]

