import type { ReactNode } from "react";

/** A ruled frame: the one panel style in the app (DESIGN.md). Never nest. */
export function Card({
  title,
  description,
  action,
  children,
  className = "",
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-line bg-surface ${className}`}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 border-b border-line px-5 pb-3 pt-4">
          <div className="min-w-0">
            {title && <h2 className="font-serif text-[17px] font-medium leading-snug text-ink">{title}</h2>}
            {description && <p className="mt-0.5 text-xs leading-relaxed text-ink-3">{description}</p>}
          </div>
          {action}
        </header>
      )}
      <div className="px-5 pb-5 pt-4">{children}</div>
    </section>
  );
}

export function PageHeader({ title, description, children }: { title: string; description?: string; children?: ReactNode }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="font-serif text-[32px] font-medium leading-tight tracking-[-0.015em] text-ink">{title}</h1>
        {description && <p className="mt-1.5 max-w-[75ch] text-sm leading-relaxed text-ink-2">{description}</p>}
      </div>
      {children}
    </div>
  );
}
