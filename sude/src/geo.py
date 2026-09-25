def bbox_center(bbox):
    """
    Bounding box'ın merkez piksel koordinatını hesaplar.

    bbox formatı:
    [x1, y1, x2, y2]
    """

    x1, y1, x2, y2 = bbox

    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2

    return center_x, center_y

def bbox_center(bbox):
    """
    Bounding box'ın merkez piksel koordinatını hesaplar.

    bbox formatı:
    [x1, y1, x2, y2]
    """

    x1, y1, x2, y2 = bbox

    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2

    return center_x, center_y


def pixel_to_geo(x, y, map_metadata=None):
    """
    Piksel koordinatını gerçek dünya koordinatına dönüştürecek.

    Gerçek yarışma harita verisinin formatını henüz bilmediğimiz
    için şu anda dönüşüm yapmıyoruz.
    """

    return {
        "latitude": None,
        "longitude": None,
        "status": "waiting_for_map_metadata"
    }