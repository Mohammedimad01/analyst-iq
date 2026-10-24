"use client";

import {
  BarChart3,
  ChevronsLeft,
  ChevronsRight,
  Database,
  FileText,
  LayoutDashboard,
  Menu,
  Package,
  Settings,
  Sparkles,
  Store,
  Users,
  Workflow,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { FilterBar } from "@/components/shell/FilterBar";
import { FiltersProvider, useFilters } from "@/components/shell/FiltersProvider";
import { StatusIndicator } from "@/components/shell/StatusIndicator";
import { dataBadge } from "@/lib/workspace";

const NAV: { href: string; label: string; icon: LucideIcon; filters: boolean }[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard, filters: true },
  { href: "/sales", label: "Sales Analytics", icon: BarChart3, filters: true },
  { href: "/products", label: "Products", icon: Package, filters: true },
  { href: "/stores", label: "Stores & Channels", icon: Store, filters: true },
  { href: "/customers", label: "Customers", icon: Users, filters: true },
  { href: "/insights", label: "AI Insights", icon: Sparkles, filters: true },
  { href: "/reports", label: "Reports", icon: FileText, filters: true },
  { href: "/data", label: "Data Sources", icon: Database, filters: false },
  { href: "/automation", label: "Automation", icon: Workflow, filters: false },
  { href: "/settings", label: "Settings", icon: Settings, filters: false },
];

function Logo({ collapsed }: { collapsed: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-sm font-bold text-white">IQ</div>
      {!collapsed && <span className="text-[15px] font-semibold tracking-tight text-white">Analyst IQ</span>}
    </div>
  );
}

function NavLinks({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-col gap-0.5">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            title={collapsed ? label : undefined}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              active ? "bg-navy-line text-white" : "text-navy-ink hover:bg-navy-2 hover:text-white"
            } ${collapsed ? "justify-center px-0" : ""}`}
          >
            <Icon className="size-4 shrink-0" aria-hidden="true" />
            {collapsed ? <span className="sr-only">{label}</span> : label}
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <FiltersProvider>
      <Shell>{children}</Shell>
    </FiltersProvider>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const { workspace } = useFilters();
  const badge = dataBadge(workspace?.data_kind);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();
  const current = NAV.find((n) => (n.href === "/" ? pathname === "/" : pathname.startsWith(n.href)));

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside
        className={`sticky top-0 hidden h-screen shrink-0 flex-col bg-navy px-3 py-4 transition-[width] md:flex ${
          collapsed ? "w-16" : "w-60"
        }`}
      >
        <div className={`mb-6 px-1 ${collapsed ? "flex justify-center" : ""}`}>
          <Logo collapsed={collapsed} />
        </div>
        <NavLinks collapsed={collapsed} />
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="mt-auto flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs text-navy-ink hover:bg-navy-2 hover:text-white"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronsRight className="size-4" /> : (<><ChevronsLeft className="size-4" /> Collapse</>)}
        </button>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setMobileOpen(false)} />
          <aside className="relative flex h-full w-64 flex-col bg-navy px-3 py-4">
            <div className="mb-6 flex items-center justify-between px-1">
              <Logo collapsed={false} />
              <button onClick={() => setMobileOpen(false)} className="text-navy-ink hover:text-white" aria-label="Close navigation">
                <X className="size-5" />
              </button>
            </div>
            <NavLinks collapsed={false} onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
          <div className="flex h-14 items-center gap-3 px-4 md:px-6">
            <button className="text-ink-2 md:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
              <Menu className="size-5" />
            </button>
            <nav aria-label="Breadcrumb" className="min-w-0 text-sm">
              <span className="text-ink-3">{workspace?.organization_name ?? "Analyst IQ"}</span>
              <span className="mx-2 text-line-strong">/</span>
              <span className="font-medium text-ink">{current?.label ?? "Analyst IQ"}</span>
            </nav>
            {badge && (
              <span
                className={`hidden rounded-full px-2 py-0.5 text-[11px] font-medium sm:inline ${
                  badge.tone === "warning" ? "bg-warning-soft text-warning" : "bg-subtle text-ink-2"
                }`}
              >
                {badge.label}
              </span>
            )}
            {workspace?.read_only && (
              <span className="hidden rounded-full bg-subtle px-2 py-0.5 text-[11px] font-medium text-ink-2 sm:inline">
                Read-only
              </span>
            )}
            <div className="ml-auto">
              <StatusIndicator />
            </div>
          </div>
          {current?.filters && <FilterBar />}
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 md:px-6">{children}</main>
      </div>
    </div>
  );
}
