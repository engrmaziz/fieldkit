"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Search,
  Network,
  GitBranch,
  AlertTriangle,
  UserCheck,
} from "lucide-react";

export default function FoundryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  const tabs = [
    {
      href: "/foundry/explorer",
      label: "Explorer",
      icon: Search,
      description: "Search & Keyset Pagination",
    },
    {
      href: "/foundry/graph",
      label: "Graph Explorer",
      icon: Network,
      description: "Ontology Link Traversal",
    },
    {
      href: "/foundry/lineage",
      label: "Lineage",
      icon: GitBranch,
      description: "Provenance & OpenLineage DAG",
    },
    {
      href: "/foundry/drift",
      label: "Drift Inbox",
      icon: AlertTriangle,
      description: "Schema Shifts & LLM Proposals",
    },
    {
      href: "/foundry/review",
      label: "ER Review Queue",
      icon: UserCheck,
      description: "Human-in-the-Loop Adjudication",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Sub-Navigation Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800/80 gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center space-x-2">
            <span>Enterprise Foundry</span>
            <span className="text-xs font-mono font-normal px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300">
              Halden Industrie
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Canonical data fusion, entity resolution, and governance plane
          </p>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center space-x-1 p-1 bg-slate-900/80 rounded-lg border border-slate-800 overflow-x-auto">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive =
              pathname === tab.href ||
              (tab.href === "/foundry/explorer" && pathname.startsWith("/foundry/objects"));

            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`flex items-center space-x-2 px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-all ${
                  isActive
                    ? "bg-cyan-950/80 text-cyan-300 border border-cyan-800/80 shadow-sm shadow-cyan-950"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? "text-cyan-400" : "text-slate-400"}`} />
                <span>{tab.label}</span>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Main View Area */}
      <div>{children}</div>
    </div>
  );
}
