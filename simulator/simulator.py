# simulator.py
import json
import math
import os
import random
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

from config import (
    CITIES,
    SENSORS_PER_CITY,
    DIURNAL_AMPLITUDE,
    TEMP_NOISE_STD,
    HUM_NOISE_STD,
    ANOMALY_PROBABILITY,
    ANOMALY_SPIKE_MIN,
    ANOMALY_SPIKE_MAX,
)

# ── Environment ───────────────────────────────────────────────────────────────
KAFKA_SERVERS   = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
KAFKA_TOPIC     = os.environ.get("KAFKA_TOPIC",        "iot.sensors.raw")
EMIT_INTERVAL   = float(os.environ.get("EMIT_INTERVAL_MS", "500")) / 1000.0


# ── Topic bootstrap ───────────────────────────────────────────────────────────
def ensure_topic(bootstrap_servers: str, topic: str, num_partitions: int = 10) -> None:
    """
    Create the Kafka topic if it does not already exist.
    num_partitions = number of cities, so each city maps to one partition
    when using city as the message key.
    """
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    existing = admin.list_topics(timeout=10).topics

    if topic in existing:
        print(f"[INFO] Topic '{topic}' already exists — skipping creation")
        return

    new_topic = NewTopic(
        topic,
        num_partitions=num_partitions,
        replication_factor=1,           # single-broker local setup
        config={
            "retention.ms": str(7 * 24 * 60 * 60 * 1000),  # 7 days
            "compression.type": "snappy",
        },
    )
    futures = admin.create_topics([new_topic])
    for t, future in futures.items():
        try:
            future.result()
            print(f"[INFO] Topic '{t}' created ({num_partitions} partitions)")
        except Exception as e:
            print(f"[WARN] Could not create topic '{t}': {e}")


# ── Sensor reading generation ─────────────────────────────────────────────────
def make_reading(city_cfg: dict, sensor_id: str) -> dict:
    """
    Generate one sensor reading for a given city/sensor.

    Temperature model:
        base_temp
        + diurnal sine wave  (peaks at 14:00 UTC, trough at 04:00 UTC)
        + Gaussian noise
        + optional anomaly spike

    Humidity model:
        base_hum
        - scaled inverse of diurnal offset  (warmer → drier)
        + Gaussian noise
        clamped to [0, 100]
    """
    hour = datetime.now(timezone.utc).hour

    # Sine wave: period=24h, peak at hour=14
    diurnal = DIURNAL_AMPLITUDE * math.sin(math.pi * (hour - 4) / 12.0)

    temperature = city_cfg["base_temp"] + diurnal + random.gauss(0, TEMP_NOISE_STD)
    humidity    = city_cfg["base_hum"]  - diurnal * 0.8 + random.gauss(0, HUM_NOISE_STD)
    humidity    = max(0.0, min(100.0, humidity))

    is_anomaly = random.random() < ANOMALY_PROBABILITY
    if is_anomaly:
        spike       = random.uniform(ANOMALY_SPIKE_MIN, ANOMALY_SPIKE_MAX)
        temperature += random.choice([-1, 1]) * spike

    return {
        "event_id":    str(uuid.uuid4()),
        "sensor_id":   sensor_id,
        "city":        city_cfg["city"],
        "country":     city_cfg["country"],
        "latitude":    city_cfg["lat"],
        "longitude":   city_cfg["lon"],
        "temperature": round(temperature, 2),
        "humidity":    round(humidity, 2),
        "is_anomaly":  is_anomaly,
        "event_ts":    datetime.now(timezone.utc).isoformat(),
    }


# ── Delivery callback ─────────────────────────────────────────────────────────
def on_delivery(err, msg):
    if err:
        print(f"[ERROR] Delivery failed | topic={msg.topic()} | {err}")


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    # Build sensor list: [(city_cfg, sensor_id), ...]
    sensors = [
        (city, f"{city['city'][:3].upper()}-{i:03d}")
        for city in CITIES
        for i in range(1, SENSORS_PER_CITY + 1)
    ]

    print(f"[INFO] IoT Simulator starting")
    print(f"[INFO]   Broker  : {KAFKA_SERVERS}")
    print(f"[INFO]   Topic   : {KAFKA_TOPIC}")
    print(f"[INFO]   Sensors : {len(sensors)} ({len(CITIES)} cities × {SENSORS_PER_CITY})")
    print(f"[INFO]   Interval: {EMIT_INTERVAL * 1000:.0f} ms")

    ensure_topic(KAFKA_SERVERS, KAFKA_TOPIC, num_partitions=len(CITIES))

    producer = Producer({
        "bootstrap.servers":      KAFKA_SERVERS,
        "client.id":              "iot-simulator",
        "acks":                   "all",        # wait for leader + all ISR replicas
        "compression.type":       "snappy",
        "linger.ms":              50,           # batch messages for 50ms before sending
        "batch.size":             65536,        # 64KB batch size
    })

    tick = 0
    try:
        while True:
            for city_cfg, sensor_id in sensors:
                reading = make_reading(city_cfg, sensor_id)
                producer.produce(
                    topic=KAFKA_TOPIC,
                    key=city_cfg["city"],                       # partition by city
                    value=json.dumps(reading).encode("utf-8"),
                    callback=on_delivery,
                )

            # Poll to trigger delivery callbacks and flush internal queue
            producer.poll(0)

            tick += 1
            if tick % 100 == 0:
                print(f"[INFO] Tick {tick} — {len(sensors)} readings emitted")

            time.sleep(EMIT_INTERVAL)

    except KeyboardInterrupt:
        print("[INFO] Shutting down — flushing producer...")
    finally:
        producer.flush(timeout=10)
        print("[INFO] Producer flushed. Bye.")


if __name__ == "__main__":
    main()