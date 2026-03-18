# config.py
# Central configuration: cities, sensor layout, physical constants

CITIES = [
    {"city": "Rome",      "country": "IT", "lat": 41.90, "lon": 12.49, "base_temp": 18.0, "base_hum": 65.0},
    {"city": "Milan",     "country": "IT", "lat": 45.47, "lon":  9.19, "base_temp": 14.0, "base_hum": 70.0},
    {"city": "London",    "country": "GB", "lat": 51.51, "lon": -0.13, "base_temp": 11.0, "base_hum": 75.0},
    {"city": "Berlin",    "country": "DE", "lat": 52.52, "lon": 13.40, "base_temp": 10.0, "base_hum": 72.0},
    {"city": "Paris",     "country": "FR", "lat": 48.85, "lon":  2.35, "base_temp": 13.0, "base_hum": 73.0},
    {"city": "Madrid",    "country": "ES", "lat": 40.42, "lon": -3.70, "base_temp": 17.0, "base_hum": 55.0},
    {"city": "Amsterdam", "country": "NL", "lat": 52.37, "lon":  4.90, "base_temp": 10.0, "base_hum": 80.0},
    {"city": "Vienna",    "country": "AT", "lat": 48.21, "lon": 16.37, "base_temp": 12.0, "base_hum": 68.0},
    {"city": "Warsaw",    "country": "PL", "lat": 52.23, "lon": 21.01, "base_temp":  8.0, "base_hum": 74.0},
    {"city": "Lisbon",    "country": "PT", "lat": 38.72, "lon": -9.14, "base_temp": 17.0, "base_hum": 60.0},
]

# How many independent sensors per city
SENSORS_PER_CITY = 3

# Physical validation bounds (used by downstream Silver job too — keep in sync)
TEMP_MIN, TEMP_MAX = -50.0, 80.0
HUM_MIN,  HUM_MAX  =   0.0, 100.0

# Diurnal cycle amplitude in °C (peak at 14:00, trough at 04:00)
DIURNAL_AMPLITUDE = 4.0

# Gaussian noise standard deviations
TEMP_NOISE_STD = 0.8
HUM_NOISE_STD  = 2.0

# Anomaly injection probability (simulates sensor fault)
ANOMALY_PROBABILITY = 0.05
ANOMALY_SPIKE_MIN   = 10.0
ANOMALY_SPIKE_MAX   = 20.0