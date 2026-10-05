/** Fleetwright mark: three lanes converging on one beacon — many workers, one claim. */
export function FleetMark({ className, title }: { className?: string; title?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <path
        d="M12 9.2 4.2 20.4M12 9.2v11.2M12 9.2l7.8 11.2"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.1"
        strokeLinecap="round"
      />
      <circle cx="12" cy="5.4" r="2.6" fill="var(--beacon)" />
    </svg>
  );
}
