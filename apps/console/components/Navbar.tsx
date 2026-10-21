"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth, DEMO_USERS } from "@/lib/auth-context";
import {
  ShieldAlert,
  Database,
  Bot,
  Wrench,
  FileText,
  ChevronDown,
  Activity,
  Layers,
  Camera,
  ScanEye,
} from "lucide-react";
import { useState } from "react";

export default function Navbar() {
  const pathname = usePathname();
  const { currentUser, setUser } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const navLinks = [
    { href: "/foundry/explorer", label: "Foundry", icon: Database, active: pathname?.startsWith("/foundry") },
    { href: "/assistant", label: "Assistant", icon: Bot, badge: "P2", active: pathname?.startsWith("/assistant") },
    { href: "/observe", label: "Observe", icon: Activity, badge: "P7", active: pathname?.startsWith("/observe") },
    { href: "/copilot", label: "Copilot", icon: Wrench, badge: "P3", active: pathname?.startsWith("/copilot") },
    { href: "/docai", label: "Doc AI", icon: FileText, badge: "P4", active: pathname?.startsWith("/docai") },
    { href: "/vision", label: "Vision", icon: Camera, badge: "P5", active: pathname?.startsWith("/vision") },
    { href: "/inspection", label: "InspectAI", icon: ScanEye, badge: "P6", active: pathname?.startsWith("/inspection") },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 md:px-6 h-16 flex items-center justify-between">
        {/* Brand & Title */}
        <div className="flex items-center space-x-6">
          <Link href="/foundry/explorer" className="flex items-center space-x-3 group">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-cyan-600 to-teal-400 flex items-center justify-center shadow-lg shadow-cyan-900/40 border border-cyan-400/30">
              <Layers className="w-5 h-5 text-slate-950" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold tracking-tight text-slate-100 text-sm">FIELDKIT</span>
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-cyan-950/80 border border-cyan-800 text-cyan-400 font-semibold">
                  P1 FOUNDRY
                </span>
              </div>
              <span className="text-[11px] text-slate-400 font-mono block">Halden Industrie Operations</span>
            </div>
          </Link>

          {/* Main Navigation */}
          <nav className="hidden md:flex items-center space-x-1 pl-4 border-l border-slate-800">
            {navLinks.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center space-x-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    item.active
                      ? "bg-slate-800/90 text-cyan-400 border border-slate-700/60 shadow-sm"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Right Section: RLS Status & User Switcher */}
        <div className="flex items-center space-x-4">
          {/* Plant RLS badge */}
          <div className="hidden lg:flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-slate-900/90 border border-slate-800 text-slate-300">
            <Activity className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            <span>RLS:</span>
            <span
              className={`font-semibold ${
                currentUser.plant ? "text-cyan-400" : "text-amber-400"
              }`}
            >
              {currentUser.plant ? currentUser.plant : "ALL PLANTS (ADMIN)"}
            </span>
          </div>

          {/* User Persona Switcher Dropdown */}
          <div className="relative">
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center space-x-2.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all text-left"
            >
              <div className="w-6 h-6 rounded-full bg-cyan-600/30 border border-cyan-500/40 flex items-center justify-center text-[11px] font-bold text-cyan-300">
                {currentUser.name.charAt(0)}
              </div>
              <div className="text-xs">
                <span className="font-medium text-slate-200 block leading-tight">{currentUser.name}</span>
                <span className="text-[10px] text-slate-400 font-mono block leading-tight">
                  {currentUser.roles[0]} {currentUser.plant ? `• ${currentUser.plant}` : "• Global"}
                </span>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 mt-2 w-64 rounded-lg bg-slate-900 border border-slate-800 shadow-xl py-1 z-50">
                <div className="px-3 py-2 border-b border-slate-800">
                  <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">
                    Switch Test Persona (RLS Demo)
                  </span>
                </div>
                {DEMO_USERS.map((user) => (
                  <button
                    key={user.username}
                    onClick={() => {
                      setUser(user);
                      setDropdownOpen(false);
                    }}
                    className={`w-full px-3 py-2 text-left flex items-center justify-between text-xs transition-colors hover:bg-slate-800/80 ${
                      user.username === currentUser.username
                        ? "bg-slate-800/50 text-cyan-400 font-medium"
                        : "text-slate-300"
                    }`}
                  >
                    <div>
                      <div className="font-semibold">{user.name}</div>
                      <div className="text-[10px] text-slate-400 font-mono">
                        {user.roles.join(", ")}
                      </div>
                    </div>
                    <span
                      className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                        user.plant
                          ? "bg-slate-800 border-slate-700 text-slate-300"
                          : "bg-amber-950/40 border-amber-800/60 text-amber-300"
                      }`}
                    >
                      {user.plant || "Global"}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
