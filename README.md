# 🌡️ IoT Sensor Lakehouse

A fully local, Docker-based data engineering lab that simulates an end-to-end IoT streaming pipeline — from sensor data generation to a live Grafana dashboard — using only open source tools.

Built for learning and portfolio purposes, every tool in this stack maps directly to a production AWS equivalent.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Medallion Architecture](#medallion-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Services & Ports](#services--ports)
- [Pipeline Walkthrough](#pipeline-walkthrough)
- [Learning Goals](#learning-goals)
- [AWS Equivalents](#aws-equivalents)

---

## Overview

A Python-based IoT simulator generates fake temperature and humidity readings for 10 European cities, publishing them as JSON events to **Redpanda** (Kafka-compatible message broker). **Apache Spark Structured Streaming** consumes the events, adds an ingestion timestamp, and writes them as **Parquet** files to a **MinIO** (S3-compatible) data lake using the **Apache Iceberg** open table format.

A batch layer built on **dbt Core** and **Trino** handles analytical transformations across the Medallion Architecture layers (Bronze → Silver → Gold). Final aggregations land in **PostgreSQL** as the serving layer, and **Grafana** provides live and historical dashboards.

```
IoT Simulator → Redpanda → Spark Streaming → MinIO/Iceberg (Bronze)
                                                      ↓
                                             Spark Batch (Silver)
                                                      ↓
                                             dbt + Trino (Gold)
                                                      ↓
                                             PostgreSQL (Serving)
                                                      ↓
                                             Grafana (Dashboards)
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        STREAMING PLANE                           │
│                                                                  │
│  [IoT Simulator]  →  [Redpanda]  →  [Spark Structured Streaming]│
│   Python producer     Kafka API      Reads topic, adds           │
│   10 cities           iot.sensors.raw  ingestion_ts              │
│   3 sensors/city      7-day retention                            │
│                                           ↓                      │
│                                    [MinIO — Bronze]              │
│                                    iceberg.bronze                │
│                                    .sensor_readings_raw          │
└──────────────────────────────────────────────────────────────────┘
                               ↓  Spark Batch (every 5 min)
┌──────────────────────────────────────────────────────────────────┐
│                        LAKEHOUSE PLANE                           │
│                                                                  │
│  Bronze → [Spark Batch] → Silver   Dedup, validate, cast types  │
│  Silver → [dbt + Trino] → Gold     Hourly/daily aggregations    │
│                                                                  │
│  All tables managed by Apache Iceberg on MinIO (S3-compatible)  │
└──────────────────────────────────────────────────────────────────┘
                               ↓  dbt loads serving tables
┌──────────────────────────────────────────────────────────────────┐
│                   SERVING & VISUALIZATION PLANE                  │
│                                                                  │
│  [PostgreSQL]  →  [Grafana]                                      │
│  fact_sensor_readings    Live temperature/humidity time series   │
│  agg_hourly_city         City comparison heatmap                 │
│  agg_daily_city          Daily summary table                     │
│  dim_cities              Anomaly rate gauges                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Medallion Architecture

Data is organized into three quality layers, each stored as an Iceberg table on MinIO:

| Layer | Location | Content | Written By |
|-------|----------|---------|------------|
| 🥉 **Bronze** | `s3a://lakehouse/bronze/` | Raw, unmodified events + `ingestion_ts`. Append-only. | Spark Streaming |
| 🥈 **Silver** | `s3a://lakehouse/silver/` | Deduplicated, validated, typed. Partitioned by `(city, event_date)`. | Spark Batch |
| 🥇 **Gold** | `s3a://lakehouse/gold/` | Hourly/daily aggregations per city. Business-ready. | dbt + Trino |

**Bronze** is your safety net — raw data preserved exactly as received, forever reprocessable.  
**Silver** is your source of truth — every row is trusted, validated, and deduplicated.  
**Gold** is your serving layer — pre-aggregated answers optimized for fast dashboard queries.

---

## Tech Stack

| Service | Image | Purpose |
|---------|-------|---------|
| **Redpanda** | `redpandadata/redpanda:v23.3.11` | Kafka-compatible event streaming broker |
| **Redpanda Console** | `redpandadata/console:v2.4.3` | Web UI to inspect topics, offsets, messages |
| **IoT Simulator** | Custom Python 3.11 | Kafka producer — generates fake sensor events |
| **MinIO** | `minio/minio:latest` | S3-compatible object store — all Parquet files |
| **Iceberg REST Catalog** | `tabulario/iceberg-rest` | Iceberg table metadata service |
| **Spark Master** | `bitnami/spark:3.5` (custom) | Spark master — runs streaming + batch jobs |
| **Spark Worker ×2** | `bitnami/spark:3.5` (custom) | Spark workers (4 cores / 8 GB each) |
| **Trino** | `trinodb/trino:435` | Distributed SQL engine over Iceberg tables |
| **dbt** | Custom Python 3.11 | SQL transformation layer (Silver → Gold) |
| **PostgreSQL** | `postgres:15` | Serving layer — feeds Grafana dashboards |
| **Grafana** | `grafana/grafana:10.3` | Live and historical dashboards |

---

## Project Structure

```
iot-lakehouse/
├── docker-compose.yml
├── .env
├── Makefile
│
├── simulator/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py              # Cities, sensor config, physical constants
│   └── simulator.py           # Kafka producer loop
│
├── spark/
│   ├── Dockerfile
│   ├── jars/                  # Iceberg + Kafka connector JARs
│   ├── jobs/
│   │   ├── streaming_bronze.py   # Kafka → Bronze Iceberg (Streaming)
│   │   └── batch_silver.py       # Bronze → Silver (cleaning, dedup)
│   └── conf/
│       └── spark-defaults.conf   # S3A, Iceberg catalog config
│
├── dbt/
│   ├── Dockerfile
│   ├── dbt_project.yml
│   ├── profiles.yml           # Trino connection
│   ├── models/
│   │   ├── staging/           # Thin views over Silver
│   │   ├── intermediate/      # Cleaning + anomaly flags
│   │   └── marts/             # Gold aggregations + PostgreSQL serving tables
│   └── tests/                 # Data quality assertions
│
├── trino/
│   ├── catalog/
│   │   ├── iceberg.properties    # Iceberg connector (→ MinIO)
│   │   └── postgresql.properties # PostgreSQL connector
│   └── config.properties
│
├── postgres/
│   └── init.sql               # Schema: facts, aggregates, dim_cities
│
└── grafana/
    └── provisioning/
        ├── datasources/       # Auto-configure PostgreSQL datasource
        └── dashboards/        # Pre-built dashboard JSON
```

---

## Prerequisites

- **Docker Engine** + **Docker Compose V2** (`docker compose version` → v2.x)
- **~18 GB RAM** available for the full stack (Spark workers are the heaviest consumers)
- **~10 GB disk** for Docker images + MinIO data volumes

```bash
# Fedora / RHEL
sudo dnf install -y docker docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
```

---

## Getting Started

### 1. Clone and configure

```bash
git clone https://github.com/your-username/iot-lakehouse.git
cd iot-lakehouse
cp .env.example .env      # edit credentials if needed
```

### 2. Start the simulator + Redpanda first

```bash
docker compose up -d redpanda redpanda-console iot-simulator

# Verify messages are flowing
docker compose logs -f iot-simulator
# Open Redpanda Console → http://localhost:8080
# Topics → iot.sensors.raw → Messages
```

### 3. Bootstrap MinIO buckets

```bash
docker compose up -d minio
docker compose exec minio mc alias set local http://localhost:9000 minioadmin minioadmin123
docker compose exec minio mc mb local/lakehouse
```

### 4. Start the full stack

```bash
docker compose up -d
```

### 5. Submit the Bronze streaming job

```bash
docker compose exec spark-master spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0,\
             org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,\
             org.apache.hadoop:hadoop-aws:3.3.4 \
  /opt/spark/jobs/streaming_bronze.py
```

### 6. Run the Silver batch job

```bash
docker compose exec spark-master spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0,\
             org.apache.hadoop:hadoop-aws:3.3.4 \
  /opt/spark/jobs/batch_silver.py
```

### 7. Run dbt transformations

```bash
docker compose exec dbt bash
# Inside container:
dbt deps
dbt run
dbt test
```

---

## Services & Ports

| Service | URL | Credentials |
|---------|-----|-------------|
| Redpanda Console | http://localhost:8080 | No login |
| MinIO Console | http://localhost:9001 | `minioadmin` / `minioadmin123` |
| Spark Master UI | http://localhost:4040 | No login |
| Spark Worker 1 | http://localhost:8081 | No login |
| Spark Worker 2 | http://localhost:8082 | No login |
| Trino UI | http://localhost:8090 | user: `trino` (no password) |
| Grafana | http://localhost:3000 | `admin` / `grafana123` |
| Iceberg REST | http://localhost:8181 | REST API |

---

## Pipeline Walkthrough

### IoT Simulator → Redpanda
The simulator generates readings for **10 European cities × 3 sensors** every 500ms. Each reading includes temperature (with a realistic diurnal sine wave + Gaussian noise), humidity, coordinates, and a 5% random anomaly spike. Messages are keyed by city, so all events for the same city always land on the same Kafka partition — guaranteeing per-city ordering.

### Redpanda → Spark (Bronze)
Spark Structured Streaming reads from `iot.sensors.raw`, deserializes the JSON, applies a strict schema, adds `ingestion_ts`, and writes to the Bronze Iceberg table every 30 seconds. A checkpoint stored in a Docker volume tracks Kafka offsets — if Spark restarts it resumes exactly where it left off, with no data loss and no duplicates.

### Bronze → Silver (Spark Batch)
A Spark batch job runs every 5 minutes, reads new Bronze data, and applies:
- Timestamp parsing (`event_ts` string → proper `TIMESTAMP`)
- Range validation (`temperature` ∈ [-50, 80], `humidity` ∈ [0, 100])
- Deduplication by `event_id` (keep latest `ingestion_ts`)
- `MERGE INTO` Silver — inserts only records not already present

### Silver → Gold (dbt + Trino)
dbt models run over Trino, which queries the Silver Iceberg table on MinIO directly. Models compute hourly and daily aggregations per city: avg/min/max temperature, avg humidity, anomaly count and rate. Results are materialized as Gold Iceberg tables and loaded into PostgreSQL for Grafana.

### PostgreSQL → Grafana
Grafana reads from four PostgreSQL tables using `$__timeFilter()` for dynamic time-range filtering. The main dashboard includes a live temperature time series, humidity trends, a city heatmap, anomaly rate gauges, and a daily summary table.

---

## Learning Goals

| Tool | What this project teaches |
|------|--------------------------|
| **Redpanda / Kafka** | Topics, partitions, consumer groups, offsets, retention, key-based routing |
| **Spark Streaming** | Structured Streaming, micro-batches, checkpointing, watermarks, Kafka connector |
| **Spark Batch** | DataFrame API, PySpark, MERGE INTO, window functions |
| **Apache Iceberg** | Open table format, snapshots, time travel, schema evolution, ACID on object storage |
| **MinIO** | S3-compatible object storage, bucket layout, Parquet file organization |
| **Trino** | Distributed SQL, Iceberg connector, federated queries across catalogs |
| **dbt Core** | Models, sources, tests, documentation, lineage DAG, incremental materializations |
| **PostgreSQL** | Serving layer design, indexing for time-series queries |
| **Grafana** | Dashboard variables, time-range macros, panel types, alerting |

---

## AWS Equivalents

This stack is designed so that migrating to AWS is mostly a configuration change:

| Local | AWS |
|-------|-----|
| Redpanda | Amazon MSK (Managed Kafka) |
| MinIO | Amazon S3 |
| Iceberg REST Catalog | AWS Glue Data Catalog |
| Spark (Docker) | AWS Glue / Amazon EMR |
| Trino | Amazon Athena |
| dbt Core | dbt Core on EC2 / dbt Cloud |
| PostgreSQL | Amazon RDS PostgreSQL |
| Grafana | Amazon Managed Grafana |

---

## License

MIT
