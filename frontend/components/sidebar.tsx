"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { AppRole } from "@/lib/types";


const navigation = [
  {
    href: "/dashboard",
    label: "Overview",
    icon: "grid",
    roles: [
      "AP_CLERK",
      "REVIEWER",
      "ADMIN",
    ] as AppRole[],
  },
  {
    href: "/invoices",
    label: "Invoices",
    icon: "file",
    roles: [
      "AP_CLERK",
      "REVIEWER",
      "ADMIN",
    ] as AppRole[],
  },
  {
    href: "/reviews",
    label: "Review queue",
    icon: "review",
    roles: [
      "REVIEWER",
      "ADMIN",
    ] as AppRole[],
  },
];


function NavIcon({
  name,
}: {
  name: string;
}) {
  if (name === "file") {
    return (
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path d="M7 3h7l4 4v14H7z" />
        <path d="M14 3v5h5M10 12h5M10 16h5" />
      </svg>
    );
  }

  if (name === "review") {
    return (
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path d="M6 3h12v18H6z" />
        <path d="M9 8h6M9 12h6M9 16h3" />
      </svg>
    );
  }

  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" />
    </svg>
  );
}


export function Sidebar({
  role,
}: {
  role: AppRole;
}) {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          D
        </div>
        <div>
          <div className="brand-name">
            DocuFlow
          </div>
          <div className="brand-subtitle">
            AP Operations
          </div>
        </div>
      </div>

      <nav
        className="sidebar-nav"
        aria-label="Primary navigation"
      >
        <div className="nav-label">
          Workspace
        </div>

        {navigation
          .filter((item) =>
            item.roles.includes(role),
          )
          .map((item) => {
            const active =
              pathname === item.href ||
              pathname.startsWith(
                `${item.href}/`,
              );

            return (
              <Link
                key={item.href}
                href={item.href}
                className={
                  active
                    ? "nav-item nav-item-active"
                    : "nav-item"
                }
              >
                <span className="nav-icon">
                  <NavIcon
                    name={item.icon}
                  />
                </span>
                <span>{item.label}</span>
              </Link>
            );
          })}
      </nav>

      <div className="sidebar-footer">
        <div className="system-state">
          <span className="live-dot" />
          <div>
            <div className="system-title">
              Systems operational
            </div>
            <div className="system-copy">
              Local portfolio environment
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
