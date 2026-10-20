"use client";

import React, { useState } from "react";
import { Ticket } from "./types";
import {
  Inbox,
  Clock,
  AlertTriangle,
  CheckCircle2,
  AlertOctagon,
  Search,
  Filter,
  ShieldCheck,
  Building2,
  Sparkles,
} from "lucide-react";

interface TicketInboxProps {
  tickets: Ticket[];
  selectedTicketId: string;
  onSelectTicket: (ticket: Ticket) => void;
}

export default function TicketInbox({
  tickets,
  selectedTicketId,
  onSelectTicket,
}: TicketInboxProps) {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [queueFilter, setQueueFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const awaitingCount = tickets.filter((t) => t.status === "awaiting_approval").length;

  const filteredTickets = tickets.filter((t) => {
    if (statusFilter !== "all" && t.status !== statusFilter) return false;
    if (queueFilter !== "all" && t.queue !== queueFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const match =
        t.ticket_id.toLowerCase().includes(q) ||
        t.customer_name.toLowerCase().includes(q) ||
        t.order_id.toLowerCase().includes(q) ||
        t.raw_text.toLowerCase().includes(q);
      if (!match) return false;
    }
    return true;
  });

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case "critical":
        return "bg-rose-950/80 text-rose-300 border-rose-800";
      case "high":
        return "bg-amber-950/80 text-amber-300 border-amber-800";
      case "medium":
        return "bg-cyan-950/80 text-cyan-300 border-cyan-800";
      default:
        return "bg-slate-800 text-slate-400 border-slate-700";
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "awaiting_approval":
        return {
          label: "APPROVAL REQUIRED",
          style: "bg-amber-500/10 text-amber-400 border-amber-500/30",
          icon: AlertTriangle,
        };
      case "completed":
        return {
          label: "RESOLVED",
          style: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
          icon: CheckCircle2,
        };
      case "escalated":
        return {
          label: "LEGAL / LEAD ESCALATION",
          style: "bg-rose-500/10 text-rose-400 border-rose-500/30",
          icon: AlertOctagon,
        };
      default:
        return {
          label: "IN PROGRESS",
          style: "bg-slate-800 text-slate-400 border-slate-700",
          icon: Clock,
        };
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-900/60 border border-slate-800/80 rounded-xl overflow-hidden shadow-xl backdrop-blur-md">
      {/* Header & Status Tabs */}
      <div className="p-4 border-b border-slate-800 space-y-3 bg-slate-950/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Inbox className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-semibold tracking-wide text-slate-100 uppercase">
              Triage Inbox
            </h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-mono">
              {filteredTickets.length}
            </span>
          </div>

          {awaitingCount > 0 && (
            <div className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-[11px] font-mono text-amber-300">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
              <span>{awaitingCount} Awaiting Gate</span>
            </div>
          )}
        </div>

        {/* Search & Queue Filter */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-500" />
            <input
              type="text"
              placeholder="Search ticket, customer, PO..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 text-slate-200 text-xs pl-8 pr-3 py-1.5 rounded-lg focus:outline-none focus:border-cyan-500 placeholder-slate-500 font-mono"
            />
          </div>

          <div className="relative">
            <Filter className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-500" />
            <select
              value={queueFilter}
              onChange={(e) => setQueueFilter(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 text-slate-200 text-xs pl-8 pr-3 py-1.5 rounded-lg focus:outline-none focus:border-cyan-500 font-mono appearance-none cursor-pointer"
            >
              <option value="all">All Queues</option>
              <option value="returns_rma">Returns & RMA</option>
              <option value="order_delivery">Order Delivery</option>
              <option value="billing_inquiry">Billing / Credit</option>
              <option value="quality_defect">Quality Defect</option>
              <option value="technical_spec">Technical Spec</option>
            </select>
          </div>
        </div>

        {/* Status Filter Badges */}
        <div className="flex items-center space-x-1.5 pt-1 overflow-x-auto text-xs">
          {[
            { id: "all", label: "All Tickets" },
            { id: "awaiting_approval", label: "Awaiting Gate", badge: awaitingCount },
            { id: "completed", label: "Resolved" },
            { id: "escalated", label: "Escalated" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all flex items-center space-x-1.5 ${
                statusFilter === tab.id
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm"
                  : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800/80"
              }`}
            >
              <span>{tab.label}</span>
              {tab.badge !== undefined && tab.badge > 0 && (
                <span className="w-4 h-4 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[9px] flex items-center justify-center font-mono">
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Ticket List */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60 p-2 space-y-1.5">
        {filteredTickets.length === 0 ? (
          <div className="text-center py-12 text-slate-500 space-y-2">
            <Inbox className="w-8 h-8 mx-auto stroke-1 text-slate-600" />
            <p className="text-xs font-mono">No support tickets match active filters</p>
          </div>
        ) : (
          filteredTickets.map((t) => {
            const isSelected = t.ticket_id === selectedTicketId;
            const statusConfig = getStatusBadge(t.status);
            const StatusIcon = statusConfig.icon;

            return (
              <div
                key={t.ticket_id}
                onClick={() => onSelectTicket(t)}
                className={`p-3 rounded-lg cursor-pointer transition-all border text-left ${
                  isSelected
                    ? "bg-slate-800/90 border-cyan-500/50 shadow-md shadow-cyan-950/30"
                    : "bg-slate-950/40 border-slate-800/60 hover:bg-slate-800/40 hover:border-slate-700/80"
                }`}
              >
                {/* Top Row: Ticket ID + Plant + Time */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-xs font-bold text-slate-100">
                      {t.ticket_id}
                    </span>
                    <span className="flex items-center space-x-1 text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 border border-slate-700">
                      <Building2 className="w-2.5 h-2.5 text-cyan-400" />
                      <span>{t.plant}</span>
                    </span>
                    <span className="text-[10px] font-mono uppercase px-1 py-0.2 rounded bg-slate-900 text-slate-400 border border-slate-800 font-bold">
                      {t.language}
                    </span>
                  </div>

                  <span className="text-[10px] text-slate-500 font-mono flex items-center space-x-1">
                    <Clock className="w-2.5 h-2.5" />
                    <span>{t.created_at}</span>
                  </span>
                </div>

                {/* Customer & Order reference */}
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="font-medium text-slate-300">{t.customer_name}</span>
                  <span className="text-[11px] font-mono text-cyan-400/90">
                    {t.order_id}
                  </span>
                </div>

                {/* Snippet */}
                <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed mb-2.5 font-sans">
                  {t.masked_text}
                </p>

                {/* Badges: Queue, Priority & Status */}
                <div className="flex items-center justify-between pt-1 border-t border-slate-800/40">
                  <div className="flex items-center space-x-1.5">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800/80 text-cyan-300 border border-slate-700">
                      {t.queue.replace("_", " ")}
                    </span>
                    <span
                      className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded border font-semibold ${getPriorityBadge(
                        t.priority
                      )}`}
                    >
                      {t.priority}
                    </span>
                  </div>

                  <div
                    className={`flex items-center space-x-1 text-[9px] font-mono px-2 py-0.5 rounded border ${statusConfig.style}`}
                  >
                    <StatusIcon className="w-2.5 h-2.5" />
                    <span>{statusConfig.label}</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
