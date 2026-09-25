def detect_vehicles(image_path):
    """
    Şimdilik gerçek araç tespit modeli yerine
    sahte (mock) sonuç döndürüyoruz.
    """

    detections = [
        {
            "vehicle_id": "V001",
            "class": "truck",
            "confidence": 0.94,
            "bbox": [410, 250, 480, 310]
        },
        {
            "vehicle_id": "V002",
            "class": "car",
            "confidence": 0.88,
            "bbox": [150, 100, 190, 135]
        }
    ]

    return detections