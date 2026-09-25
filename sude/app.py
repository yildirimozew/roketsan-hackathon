from src.detector import detect_vehicles
from src.geo import bbox_center, pixel_to_geo
from src.reports import (
    load_reports,
    get_reports_by_region
)
from src.evidence import create_movement_evidence


detections = detect_vehicles("test.jpg")

print("Tespit edilen araçlar:\n")

for vehicle in detections:

    # Bounding box merkezini bul
    center_x, center_y = bbox_center(vehicle["bbox"])

    # Merkez pikseli coğrafi koordinata çevirmeyi dene
    geo_location = pixel_to_geo(center_x, center_y)

    print(f"Araç ID: {vehicle['vehicle_id']}")
    print(f"Tür: {vehicle['class']}")
    print(f"Güven: {vehicle['confidence']}")
    print(f"Bounding Box: {vehicle['bbox']}")
    print(f"Merkez Piksel: ({center_x}, {center_y})")

    print(
        f"Gerçek Konum: "
        f"{geo_location['latitude']}, "
        f"{geo_location['longitude']}"
    )

    print(f"Geo Durumu: {geo_location['status']}")
    print("-" * 40)

from src.movement import (
    load_movements,
    get_vehicle_history,
    calculate_speeds,
    calculate_bearing,
    bearing_to_direction,
    analyze_approach
)


print("\nHAREKET KAYITLARI")
print("=" * 40)

movements = load_movements("data/movement.csv")

v001_history = get_vehicle_history(
    movements,
    "V001"
)

for record in v001_history:
    print(
        record["timestamp"],
        "->",
        record["lat"],
        record["lon"]
    )
print("\nHIZ ANALİZİ")
print("=" * 40)

speeds = calculate_speeds(v001_history)

for speed_data in speeds:
    print(
        f"{speed_data['from']} -> {speed_data['to']} | "
        f"Mesafe: {speed_data['distance_km']:.3f} km | "
        f"Hız: {speed_data['speed_kmh']:.2f} km/h"
    )
print("\nYÖN ANALİZİ")
print("=" * 40)

first = v001_history[0]
last = v001_history[-1]

bearing = calculate_bearing(
    first["lat"],
    first["lon"],
    last["lat"],
    last["lon"]
)

direction = bearing_to_direction(bearing)

print(f"Yön açısı: {bearing:.2f}°")
print(f"Hareket yönü: {direction}")


print("\nÜSSE YAKLAŞMA ANALİZİ")
print("=" * 40)

# Bunlar sadece geliştirme için kullandığımız sahte koordinatlardır.
MOCK_BASE_LAT = 39.9200
MOCK_BASE_LON = 32.8525

approach = analyze_approach(
    v001_history,
    MOCK_BASE_LAT,
    MOCK_BASE_LON
)

for item in approach["distances"]:
    print(
        f"{item['timestamp']} -> "
        f"Üsse mesafe: {item['distance_km']:.3f} km"
    )

print()

print(
    f"İlk mesafe: "
    f"{approach['first_distance_km']:.3f} km"
)

print(
    f"Son mesafe: "
    f"{approach['last_distance_km']:.3f} km"
)

print(
    f"Üsse yaklaşıyor mu?: "
    f"{approach['approaching']}"
)

print("\nSAHA RAPORLARI")
print("=" * 40)

reports = load_reports(
    "data/reports.json"
)

region_3_reports = get_reports_by_region(
    reports,
    "REGION_3"
)

for report in region_3_reports:

    print(f"Rapor ID: {report['report_id']}")
    print(f"Zaman: {report['timestamp']}")
    print(f"Bölge: {report['region']}")
    print(f"Metin: {report['text']}")
    print("-" * 40)

print("\nYAPILANDIRILMIŞ KANIT")
print("=" * 40)

movement_evidence = create_movement_evidence(
    vehicle_id="V001",
    vehicle_class="truck",
    speeds=speeds,
    direction=direction,
    approach=approach
)

for key, value in movement_evidence.items():
    print(f"{key}: {value}")