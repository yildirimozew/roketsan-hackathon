function MovementTimeline({ vehicle }) {
  return (
    <div className="movement-timeline">
      {vehicle.movementHistory.map((event, index) => (
        <div className="timeline-event" key={`${vehicle.id}-${index}`}>
          <div className={`event-dot event-${event.type}`}></div>

          <span className="event-time">{event.time}</span>

          <span className="event-text">{event.text}</span>
        </div>
      ))}
    </div>
  );
}

export default MovementTimeline;