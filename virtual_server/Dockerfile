FROM python:3.11

RUN apt-get update \
    && apt-get install -y sqlite3 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install pandas scipy numpy

WORKDIR /workspace
