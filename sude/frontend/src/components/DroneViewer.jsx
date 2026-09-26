import { vehicles } from "../data/mockData";

function DroneViewer({ selectedVehicle, onSelectVehicle }) {
  return (
    <div className="drone-viewer">
      <div className="drone-overlay">
        <span>DRONE-01</span>
        <span>LIVE ANALYSIS</span>
      </div>

      {vehicles.map((vehicle) => {
        const isSelected = selectedVehicle === vehicle.id;

        return (
          <button
            key={vehicle.id}
            className={`bounding-box ${isSelected ? "selected" : ""}`}
            style={{
              left: `${vehicle.bbox.x}%`,
              top: `${vehicle.bbox.y}%`,
              width: `${vehicle.bbox.width}%`,
              height: `${vehicle.bbox.height}%`,
            }}
            onClick={() => onSelectVehicle(vehicle.id)}
          >
            <span className="bbox-label">
              {vehicle.id} · {vehicle.type.toUpperCase()} ·{" "}
              {Math.round(vehicle.confidence * 100)}%
            </span>
          </button>
        );
      })}

      <div className="drone-crosshair">
        <span></span>
        <span></span>
      </div>
    </div>
  );
}

export default DroneViewer;