"use client";

import React from "react";
import { useAuth, DEMO_USERS } from "@/lib/auth-context";
import { UserPrincipal } from "@/lib/types";
import { User, Shield, MapPin, Sparkles, AlertCircle } from "lucide-react";

interface PersonaBarProps {
  onSelectPrompt: (promptText: string) => void;
}

export const SAMPLE_PROMPTS = [
  {
    category: "SQL",
    query: "How many purchase orders were issued in Q3 2026?",
    badge: "SQL Aggregation",
    color: "border-cyan-800/70 bg-cyan-950/40 text-cyan-300 hover:bg-cyan-900/50",
  },
  {
    category: "RAG",
    query:
      "What is the surface roughness tolerance for honing hydraulic cylinders in Hamburg?",
    badge: "RAG Policy / SOP",
    color: "border-emerald-800/70 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/50",
  },
  {
    category: "Both",
    query:
      "What is our defect rate on hydraulic valves and what does our SOP require for defective lots?",
    badge: "Hybrid Synthesis",
    color: "border-purple-800/70 bg-purple-950/40 text-purple-300 hover:bg-purple-900/50",
  },
  {
    category: "ACL",
    query:
      "Show me the confidential legal arbitration agreements and executive dispute liabilities.",
    badge: "ACL Restricted (Legal)",
    color: "border-amber-800/70 bg-amber-950/40 text-amber-300 hover:bg-amber-900/50",
  },
];

export default function PersonaBar({ onSelectPrompt }: PersonaBarProps) {
  const { currentUser, setUser } = useAuth();

  return (
    <div className="space-y-4 mb-6">
      {/* Persona Selector Bar */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Left: Active Persona Details */}
        <div className="flex items-center space-x-3.5">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 to-teal-400 flex items-center justify-center font-bold text-slate-950 text-sm shadow-md">
            {currentUser.name.charAt(0)}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-sm text-white">
                {currentUser.name}
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-950 border border-cyan-800 text-cyan-300 font-semibold">
                ACTIVE PERSONA
              </span>
            </div>
            <div className="flex items-center space-x-3 text-xs text-slate-400 font-mono mt-0.5">
              <span className="flex items-center space-x-1">
                <Shield className="w-3 h-3 text-cyan-400" />
                <span>{currentUser.roles.join(", ")}</span>
              </span>
              <span>•</span>
              <span className="flex items-center space-x-1">
                <MapPin className="w-3 h-3 text-emerald-400" />
                <span>{currentUser.plant || "Global (Admin)"}</span>
              </span>
            </div>
          </div>
        </div>

        {/* Right: Persona Quick-Switch Buttons */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-mono text-slate-500 uppercase tracking-wider mr-1 hidden lg:inline">
            Test Personas:
          </span>
          {DEMO_USERS.map((user) => {
            const isActive = user.username === currentUser.username;
            return (
              <button
                key={user.username}
                onClick={() => setUser(user)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center space-x-1.5 ${
                  isActive
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 shadow-sm"
                    : "bg-slate-950/60 text-slate-400 border border-slate-800 hover:text-slate-200 hover:bg-slate-800/60 hover:border-slate-700"
                }`}
              >
                <span>{user.name.split(" ")[0]}</span>
                <span className="text-[10px] font-mono opacity-70">
                  ({user.roles[0]})
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Suggested Demonstration Prompt Chips */}
      <div className="space-y-1.5">
        <div className="flex items-center space-x-1.5 text-xs text-slate-400 font-mono">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          <span>Interactive Benchmark Prompts (Click to test routing & permissions):</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {SAMPLE_PROMPTS.map((item, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => onSelectPrompt(item.query)}
              className={`p-2.5 rounded-lg border text-left transition-all flex items-start justify-between group ${item.color}`}
            >
              <div className="space-y-1 pr-2">
                <span className="text-[10px] font-mono uppercase tracking-wider font-semibold opacity-90 block">
                  {item.badge}
                </span>
                <p className="text-xs font-sans text-slate-200 group-hover:text-white line-clamp-2">
                  {item.query}
                </p>
              </div>
              <Sparkles className="w-3.5 h-3.5 opacity-40 group-hover:opacity-100 transition-opacity shrink-0 mt-0.5" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
