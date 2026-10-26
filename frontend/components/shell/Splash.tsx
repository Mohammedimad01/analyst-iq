"use client";

import { useEffect, useState } from "react";

import { LogoMark, TAGLINE } from "@/components/shell/Brand";

const SLOW_MS = 4000; // after this, explain the free-tier API cold start (up to about a minute)
const FADE_MS = 450;

/**
 * Full-screen brand splash shown while the workspace's first API call is in flight. It is part of the server
 * render, so it covers the first paint, then fades out once data (or an error) arrives.
 */
export function Splash({ loading }: { loading: boolean }) {
  const [phase, setPhase] = useState<"show" | "fade" | "gone">("show");
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (loading) {
      const t = setTimeout(() => setSlow(true), SLOW_MS);
      return () => clearTimeout(t);
    }
    const fade = setTimeout(() => setPhase("fade"), 0);
    const gone = setTimeout(() => setPhase("gone"), FADE_MS);
    return () => {
      clearTimeout(fade);
      clearTimeout(gone);
    };
  }, [loading]);

  if (phase === "gone") return null;
  return (
    <div
      className={`fixed inset-0 z-50 flex flex-col items-center justify-center bg-page px-6 transition-opacity duration-[450ms] motion-reduce:transition-none ${
        phase === "fade" ? "pointer-events-none opacity-0" : "opacity-100"
      }`}
      role="status"
      aria-live="polite"
      aria-label="Loading Analyst IQ"
    >
      <div className="aiq-splash-rise flex flex-col items-center text-center">
        <LogoMark className="size-14 drop-shadow-sm" />
        <p className="mt-6 font-serif text-[40px] leading-none tracking-tight text-ink sm:text-5xl">
          <span className="font-medium">Analyst</span> <span className="font-semibold italic text-primary">IQ</span>
        </p>
        <p className="mt-3 text-sm tracking-wide text-ink-2 sm:text-[15px]">{TAGLINE}</p>
        <div className="mt-9 h-px w-44 overflow-hidden bg-line" aria-hidden="true">
          <div className="aiq-splash-bar h-full w-1/3 bg-primary" />
        </div>
        <p className="mt-4 h-10 max-w-xs text-xs leading-relaxed text-ink-3">
          {slow
            ? "Waking the analytics server. Free hosting sleeps when idle, so the first load can take up to a minute."
            : "Loading your workspace…"}
        </p>
      </div>
      <p className="absolute bottom-6 text-[11px] uppercase tracking-[0.18em] text-ink-3">Retail analytics · KPIs · AI insights</p>
    </div>
  );
}
