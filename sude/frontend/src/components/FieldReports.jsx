function FieldReports({ reports, selectedVehicleId }) {
  const statusLabels = {
    supported: "DESTEKLENİYOR",
    contradicted: "ÇELİŞİYOR",
    unverified: "DOĞRULANAMADI",
  };

  return (
    <div className="reports-list">
      {reports.map((report) => {
        const isRelated = report.vehicleId === selectedVehicleId;

        return (
          <div
            key={report.id}
            className={`report-card ${isRelated ? "report-related" : ""}`}
          >
            <div className="report-top">
              <div>
                <strong>{report.id}</strong>
                <span>
                  {report.time} · {report.region}
                </span>
              </div>

              <span className={`report-status status-${report.status}`}>
                {statusLabels[report.status]}
              </span>
            </div>

            <p>{report.text}</p>

            {report.vehicleId && (
              <span className="report-vehicle">
                İlişkili araç: {report.vehicleId}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default FieldReports;