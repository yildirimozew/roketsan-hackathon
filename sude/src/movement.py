import csv


def load_movements(file_path):
    """
    CSV dosyasındaki tüm hareket kayıtlarını okur.
    """

    movements = []

    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            movements.append({
                "vehicle_id": row["vehicle_id"],
                "timestamp": row["timestamp"],
                "lat": float(row["lat"]),
                "lon": float(row["lon"])
            })

    return movements


def get_vehicle_history(movements, vehicle_id):
    """
    Belirli bir aracın hareket kayıtlarını döndürür.
    """

    history = []

    for movement in movements:
        if movement["vehicle_id"] == vehicle_id:
            history.append(movement)

    return history
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime


def distance_km(lat1, lon1, lat2, lon2):
    """
    İki GPS koordinatı arasındaki yaklaşık mesafeyi
    Haversine formülüyle kilometre cinsinden hesaplar.
    """

    earth_radius_km = 6371.0

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(delta_lon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return earth_radius_km * c


def calculate_speeds(history):
    """
    Ardışık hareket kayıtlarından ortalama hızları hesaplar.
    """

    speeds = []

    for i in range(1, len(history)):

        previous = history[i - 1]
        current = history[i]

        distance = distance_km(
            previous["lat"],
            previous["lon"],
            current["lat"],
            current["lon"]
        )

        previous_time = datetime.strptime(
            previous["timestamp"],
            "%Y-%m-%d %H:%M:%S"
        )

        current_time = datetime.strptime(
            current["timestamp"],
            "%Y-%m-%d %H:%M:%S"
        )

        time_difference = current_time - previous_time
        hours = time_difference.total_seconds() / 3600

        if hours > 0:
            speed = distance / hours
        else:
            speed = 0

        speeds.append({
            "from": previous["timestamp"],
            "to": current["timestamp"],
            "distance_km": distance,
            "speed_kmh": speed
        })

    return speeds
def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    İki GPS noktası arasındaki hareket yönünü derece olarak hesaplar.

    0°   = Kuzey
    90°  = Doğu
    180° = Güney
    270° = Batı
    """

    lat1 = radians(lat1)
    lat2 = radians(lat2)

    delta_lon = radians(lon2 - lon1)

    x = sin(delta_lon) * cos(lat2)

    y = (
        cos(lat1) * sin(lat2)
        - sin(lat1) * cos(lat2) * cos(delta_lon)
    )

    bearing = atan2(x, y)

    bearing = (bearing * 180 / 3.141592653589793 + 360) % 360

    return bearing


def bearing_to_direction(bearing):
    """
    Bearing değerini okunabilir yöne çevirir.
    """

    directions = [
        "Kuzey",
        "Kuzeydoğu",
        "Doğu",
        "Güneydoğu",
        "Güney",
        "Güneybatı",
        "Batı",
        "Kuzeybatı"
    ]

    index = round(bearing / 45) % 8

    return directions[index]
def analyze_approach(history, base_lat, base_lon):
    """
    Aracın her kayıtta üsse olan mesafesini hesaplar
    ve genel olarak üsse yaklaşıp yaklaşmadığını belirler.
    """

    distances = []

    for record in history:

        distance = distance_km(
            record["lat"],
            record["lon"],
            base_lat,
            base_lon
        )

        distances.append({
            "timestamp": record["timestamp"],
            "distance_km": distance
        })

    if len(distances) < 2:
        return {
            "approaching": False,
            "distances": distances
        }

    first_distance = distances[0]["distance_km"]
    last_distance = distances[-1]["distance_km"]

    approaching = last_distance < first_distance

    return {
        "approaching": approaching,
        "first_distance_km": first_distance,
        "last_distance_km": last_distance,
        "distance_change_km": last_distance - first_distance,
        "distances": distances
    }