import {
  MapContainer,
  TileLayer,
  Marker,
  Polyline,
  Popup,
  useMap,
} from "react-leaflet";

import { useEffect } from "react";
import "leaflet/dist/leaflet.css";

function MapController({ position }) {
  const map = useMap();

  useEffect(() => {
    map.setView(position, 15);
    map.invalidateSize();
  }, [position, map]);

  return null;
}

function MapViewer({ vehicle }) {
  const position = vehicle.location;
  const route = vehicle.route;

  return (
    <MapContainer
      center={position}
      zoom={15}
      className="map-container"
    >
      <MapController position={position} />

      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <Polyline positions={route} />

      <Marker position={position}>
        <Popup>
          <strong>{vehicle.id}</strong>
          <br />
          {vehicle.type}
          <br />
          Mock konum
        </Popup>
      </Marker>
    </MapContainer>
  );
}

export default MapViewer;