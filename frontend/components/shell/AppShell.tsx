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

import { LogoMark } from "@/components/shell/Brand";
import { FilterBar } from "@/components/shell/FilterBar";
import { FiltersProvider, useFilters } from "@/components/shell/FiltersProvider";
import { Splash } from "@/components/shell/Splash";
import { StatusIndicator } from "@/components/shell/StatusIndicator";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import { dataBadge } from "@/lib/workspace";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  filters: boolean;
}

const NAV_GROUPS: { title: string; items: NavItem[] }[] = [
  {
    title: "Analyse",
    items: [
      { href: "/", label: "Overview", icon: LayoutDashboard, filters: true },
      { href: "/sales", label: "Sales", icon: BarChart3, filters: true },
      { href: "/products", label: "Products", icon: Package, filters: true },
      { href: "/stores", label: "Stores & Channels", icon: Store, filters: true },
      { href: "/customers", label: "Customers", icon: Users, filters: true },
    ],
  },
  {
    title: "Act",
    items: [
      { href: "/insights", label: "AI Insights", icon: Sparkles, filters: true },
      { href: "/reports", label: "Reports", icon: FileText, filters: true },
    ],
  },
  {
    title: "Manage",
    items: [
      { href: "/data", label: "Data Sources", icon: Database, filters: false },
      { href: "/automation", label: "Automation", icon: Workflow, filters: false },
      { href: "/settings", label: "Settings", icon: Settings, filters: false },
    ],
  },
];
const NAV = NAV_GROUPS.flatMap((g) => g.items);

const isActive = (href: string, pathname: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

function Wordmark({ collapsed }: { collapsed: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2 px-2 text-ink" aria-label="Analyst IQ, overview">
      <LogoMark className="size-7 shrink-0" />
      {!collapsed && (
        <span className="flex items-baseline gap-1">
          <span className="font-serif text-[22px] font-medium tracking-tight">Analyst</span>
          <span className="font-serif text-[22px] font-semibold italic tracking-tight text-primary">IQ</span>
        </span>
      )}
    </Link>
  );
}

function NavLinks({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-col gap-5">
      {NAV_GROUPS.map((group) => (
        <div key={group.title}>
          {!collapsed && <p className="mb-1.5 px-2.5 text-[11px] font-medium text-ink-3">{group.title}</p>}
          <ul className="flex flex-col gap-px">
            {group.items.map(({ href, label, icon: Icon }) => {
              const active = isActive(href, pathname);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={onNavigate}
                    title={collapsed ? label : undefined}
                    aria-current={active ? "page" : undefined}
                    className={`flex items-center gap-2.5 rounded-md px-2.5 py-[7px] text-[13.5px] transition-colors ${
                      active ? "bg-surface font-medium text-ink ring-1 ring-line" : "text-ink-2 hover:bg-subtle hover:text-ink"
                    } ${collapsed ? "justify-center px-0" : ""}`}
                  >
                    <Icon className={`size-4 shrink-0 ${active ? "text-primary" : "text-ink-3"}`} strokeWidth={1.75} aria-hidden="true" />
                    {collapsed ? <span className="sr-only">{label}</span> : label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
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
  const { workspace, options, optionsError } = useFilters();
  const badge = dataBadge(workspace?.data_kind);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();
  const current = NAV.find((n) => isActive(n.href, pathname));

  return (
    <div className="flex min-h-screen">
      <Splash loading={!options && !optionsError} />
      <aside
        className={`sticky top-0 hidden h-screen shrink-0 flex-col border-r border-line bg-page px-3 pb-3 pt-5 transition-[width] duration-200 md:flex ${
          collapsed ? "w-16" : "w-56"
        }`}
      >
        <div className={`mb-7 ${collapsed ? "flex justify-center" : ""}`}>
          <Wordmark collapsed={collapsed} />
        </div>
        <NavLinks collapsed={collapsed} />
        <div className="mt-auto border-t border-line pt-3">
          {!collapsed && workspace && (
            <p className="mb-2 truncate px-2.5 text-xs text-ink-3" title={workspace.organization_name}>
              {workspace.organization_name}
            </p>
          )}
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-ink-3 hover:bg-subtle hover:text-ink"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronsRight className="mx-auto size-4" /> : (<><ChevronsLeft className="size-4" /> Collapse</>)}
          </button>
        </div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-ink/30" onClick={() => setMobileOpen(false)} />
          <aside className="relative flex h-full w-64 flex-col border-r border-line bg-page px-3 pt-5">
            <div className="mb-7 flex items-center justify-between">
              <Wordmark collapsed={false} />
              <button onClick={() => setMobileOpen(false)} className="text-ink-3 hover:text-ink" aria-label="Close navigation">
                <X className="size-5" />
              </button>
            </div>
            <NavLinks collapsed={false} onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-line bg-page/90 backdrop-blur-sm">
          <div className="flex h-12 items-center gap-3 px-4 md:px-8">
            <button className="text-ink-2 md:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
              <Menu className="size-5" />
            </button>
            <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-[13px]">
              <span className="hidden truncate text-ink-3 sm:inline">{workspace?.organization_name ?? "Analyst IQ"}</span>
              <span className="hidden text-line-strong sm:inline" aria-hidden="true">/</span>
              <span className="truncate font-medium text-ink">{current?.label ?? "Analyst IQ"}</span>
            </nav>
            {badge && (
              <span
                className={`hidden rounded-sm px-1.5 py-0.5 text-[11px] font-medium sm:inline ${
                  badge.tone === "warning" ? "bg-warning-soft text-warning" : "bg-subtle text-ink-2"
                }`}
              >
                {badge.label}
              </span>
            )}
            {workspace?.read_only && (
              <span className="hidden rounded-sm bg-subtle px-1.5 py-0.5 text-[11px] font-medium text-ink-2 sm:inline">Read-only</span>
            )}
            <div className="ml-auto flex items-center gap-3">
              <StatusIndicator />
              <ThemeToggle />
            </div>
          </div>
          {current?.filters && <FilterBar />}
        </header>
        <main className="mx-auto w-full max-w-[1360px] flex-1 px-4 pb-16 pt-7 md:px-8">{children}</main>
      </div>
    </div>
  );
}
