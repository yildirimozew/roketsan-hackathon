def create_movement_evidence(
    vehicle_id,
    vehicle_class,
    speeds,
    direction,
    approach
):
    """
    Bir araç hakkındaki hareket analizlerini
    tek bir yapılandırılmış kanıt altında toplar.
    """

    if speeds:
        average_speed = sum(
            item["speed_kmh"] for item in speeds
        ) / len(speeds)
    else:
        average_speed = None

    evidence = {
        "vehicle_id": vehicle_id,
        "vehicle_class": vehicle_class,
        "average_speed_kmh": average_speed,
        "direction": direction,
        "approaching_base": approach["approaching"],
        "first_distance_km": approach["first_distance_km"],
        "last_distance_km": approach["last_distance_km"],
        "distance_change_km": approach["distance_change_km"]
    }

    return evidence