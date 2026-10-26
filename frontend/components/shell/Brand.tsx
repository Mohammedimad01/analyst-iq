/** The Analyst IQ mark: three rising bars with an insight dot. Same geometry as app/icon.svg. */
export function LogoMark({ className = "size-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="7" className="fill-primary" />
      <rect x="7" y="17" width="4" height="8" rx="1" className="fill-page" />
      <rect x="14" y="13" width="4" height="12" rx="1" className="fill-page" />
      <rect x="21" y="9" width="4" height="16" rx="1" className="fill-page" />
      <circle cx="23" cy="5" r="2.25" fill="#e8925f" />
    </svg>
  );
}

export const TAGLINE = "Verified retail analytics, explained.";
