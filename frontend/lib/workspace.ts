import type { DataKind } from "@/types/api";

/** Header badge for the data actually loaded. Synthetic data is always labelled; real data is not decorated. */
export function dataBadge(kind: DataKind | undefined): { label: string; tone: "warning" | "neutral" } | null {
  if (kind === "synthetic") return { label: "Synthetic demo data", tone: "warning" };
  if (kind === "mixed") return { label: "Includes synthetic demo data", tone: "warning" };
  if (kind === "none") return { label: "No data yet", tone: "neutral" };
  return null;
}
