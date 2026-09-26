import { useState } from "react";
import "./App.css";

import DroneViewer from "./components/DroneViewer";
import MapViewer from "./components/MapViewer";
import MovementTimeline from "./components/MovementTimeline";
import FieldReports from "./components/FieldReports";

import { vehicles, fieldReports } from "./data/mockData";

function App() {
  const [selectedVehicleId, setSelectedVehicleId] = useState("V001");

  const selectedVehicle =
    vehicles.find((vehicle) => vehicle.id === selectedVehicleId) || vehicles[0];
  
  const relatedReport = fieldReports.find(
  (report) => report.vehicleId === selectedVehicleId
  );

  return (
    <div className="app">
      {/* TOP BAR */}
      <header className="topbar">
        <div>
          <h1>Situational Awareness</h1>
          <p>AI-Assisted Operations Dashboard</p>
        </div>

        <div className="system-status">
          <span className="status-dot"></span>
          SYSTEM ONLINE
        </div>
      </header>

      {/* DASHBOARD */}
      <main className="dashboard">
        {/* DRONE GÖRÜNTÜSÜ */}
        <section className="panel drone-panel">
          <div className="panel-header">
            <h2>Drone Görüntüsü</h2>
            <span>Bölge 01</span>
          </div>

          <DroneViewer
            selectedVehicle={selectedVehicleId}
            onSelectVehicle={setSelectedVehicleId}
          />
        </section>

        {/* HARİTA & ROTA */}
        <section className="panel map-panel">
          <div className="panel-header">
            <h2>Harita & Rota</h2>
            <span>Canlı Konum</span>
          </div>

          <MapViewer vehicle={selectedVehicle} />
        </section>

        {/* TESPİT EDİLEN ARAÇLAR */}
        <section className="panel vehicles-panel">
          <div className="panel-header">
            <h2>Tespit Edilen Araçlar</h2>
            <span>{vehicles.length} araç</span>
          </div>

          {vehicles.map((vehicle) => (
            <div
              key={vehicle.id}
              className={`vehicle-card ${
                selectedVehicleId === vehicle.id ? "active" : ""
              }`}
              onClick={() => setSelectedVehicleId(vehicle.id)}
            >
              <div>
                <strong>{vehicle.id}</strong>
                <p>{vehicle.type}</p>
              </div>

              <span>%{Math.round(vehicle.confidence * 100)}</span>
            </div>
          ))}
        </section>

        {/* SAHA RAPORLARI */}
        <section className="panel reports-panel">
          <div className="panel-header">
            <h2>Saha Raporları</h2>
            <span>{fieldReports.length} rapor</span>
          </div>

          <FieldReports
            reports={fieldReports}
            selectedVehicleId={selectedVehicleId}
          />
        </section>

        {/* AI RISK ASSESSMENT */}
        <section className="panel risk-panel">
          <div className="panel-header">
            <h2>AI Risk Assessment</h2>
            <span>{selectedVehicle.id}</span>
          </div>

          <div
            className={`risk-level risk-${selectedVehicle.risk.level.toLowerCase()}`}
          >
            {selectedVehicle.risk.level} RISK
          </div>

          <div className="risk-confidence">
            <span>Risk Confidence</span>
            <strong>
              %{Math.round(selectedVehicle.risk.confidence * 100)}
            </strong>
          </div>

          <p className="risk-description">
            {selectedVehicle.risk.reasoning}
          </p>

          <div className="risk-factors">
            <h3>Contributing Factors</h3>

            {selectedVehicle.risk.factors.map((factor, index) => (
              <div className="risk-factor" key={index}>
                <span>•</span>
                <p>{factor}</p>
              </div>
            ))}
          </div>

          <div className="evidence">
            <h3>Evidence</h3>

            <div className="evidence-row">
              <span>Görüntü tespiti</span>
              <strong>
                 %{Math.round(selectedVehicle.confidence * 100)}
              </strong>
            </div>

          <div className="evidence-row">
            <span>Hareket geçmişi</span>
            <strong>
              {selectedVehicle.movementHistory.length} kayıt
            </strong>
          </div>

          <div className="evidence-row">
            <span>Saha raporu</span>

            {relatedReport ? (
              <strong className={`evidence-${relatedReport.status}`}>
                {relatedReport.id} ·{" "}
                {relatedReport.status === "supported"
                  ? "Destekleniyor"
                  : relatedReport.status === "contradicted"
                  ? "Çelişiyor"
                  : "Doğrulanamadı"}
              </strong>
            ) : (
              <strong className="evidence-unverified">
                Rapor bulunamadı
              </strong>
            )}
          </div>
        </div>
      </section>

        {/* MOVEMENT TIMELINE */}
        <section className="panel timeline-panel">
          <div className="panel-header">
            <h2>Son 2 Saat</h2>
            <span>Movement Timeline</span>
          </div>

          <MovementTimeline vehicle={selectedVehicle} />
        </section>
      </main>
    </div>
  );
}

export default App;