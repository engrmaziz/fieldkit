"use client";

import React, { useState, useEffect } from "react";
import Navbar from "@/components/Navbar";
import TicketInbox from "@/components/copilot/TicketInbox";
import TicketDetailWorkspace from "@/components/copilot/TicketDetailWorkspace";
import AuditLedgerTimeline from "@/components/copilot/AuditLedgerTimeline";
import DefectInsightsView from "@/components/copilot/DefectInsightsView";
import { Ticket, DefectCluster } from "@/components/copilot/types";
import { INITIAL_TICKETS, INITIAL_DEFECT_CLUSTERS } from "@/components/copilot/mockData";
import {
  Wrench,
  Inbox,
  Layers,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  Activity,
  ShieldCheck,
} from "lucide-react";

export default function CopilotPage() {
  const [activeTab, setActiveTab] = useState<"workspace" | "audit" | "insights">("workspace");
  const [tickets, setTickets] = useState<Ticket[]>(INITIAL_TICKETS);
  const [selectedTicketId, setSelectedTicketId] = useState<string>("TICK-1001");
  const [clusters, setClusters] = useState<DefectCluster[]>(INITIAL_DEFECT_CLUSTERS);
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [notification, setNotification] = useState<string | null>(null);

  const selectedTicket =
    tickets.find((t) => t.ticket_id === selectedTicketId) || tickets[0];
  const pendingApprovalsCount = tickets.filter(
    (t) => t.status === "awaiting_approval"
  ).length;

  // Auto-dismiss notification toast
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  // Handle Supervisor Approval
  const handleApprove = async (ticketId: string) => {
    const now = new Date().toISOString();

    setTickets((prev) =>
      prev.map((t) => {
        if (t.ticket_id !== ticketId) return t;

        const updatedEvents = [
          ...(t.audit_events || []),
          {
            sequence: (t.audit_events?.length || 0),
            event_type: "HUMAN_DECISION",
            state_name: "gate",
            timestamp: now,
            prev_hash: t.audit_events?.[t.audit_events.length - 1]?.event_hash || "0000",
            event_hash: "a81024b981048190284019af48910481029410a8b9184018249108a71924018",
            payload: { decision: "approved", operator: "Lukas (Supervisor)", timestamp: now },
          },
          {
            sequence: (t.audit_events?.length || 0) + 1,
            event_type: "TOOL_EXECUTED",
            state_name: "execution",
            timestamp: now,
            prev_hash: "a81024b981048190284019af48910481029410a8b9184018249108a71924018",
            event_hash: "78102ba98104819a849182901481092841029a8b991048ba81920ca781924018",
            payload: {
              tools_executed: ["create_rma", "send_reply"],
              rma_id: "RMA-9021",
              message_id: "MSG-8819240182BA",
              mailpit_smtp: "delivered",
            },
          },
        ];

        return {
          ...t,
          status: "completed",
          audit_events: updatedEvents,
        };
      })
    );

    setNotification(`Ticket ${ticketId} approved! RMA generated & confirmation sent via Mailpit SMTP.`);
  };

  // Handle Supervisor Rejection
  const handleReject = async (ticketId: string, feedback: string) => {
    const now = new Date().toISOString();

    setTickets((prev) =>
      prev.map((t) => {
        if (t.ticket_id !== ticketId) return t;

        const updatedEvents = [
          ...(t.audit_events || []),
          {
            sequence: (t.audit_events?.length || 0),
            event_type: "HUMAN_DECISION",
            state_name: "gate",
            timestamp: now,
            prev_hash: t.audit_events?.[t.audit_events.length - 1]?.event_hash || "0000",
            event_hash: "31829401824981a8b94182901a890417bc89410a51982bca8192410a8b941097",
            payload: { decision: "rejected", feedback, operator: "Lukas (Supervisor)" },
          },
          {
            sequence: (t.audit_events?.length || 0) + 1,
            event_type: "EXECUTION_TERMINATED",
            state_name: "terminated",
            timestamp: now,
            prev_hash: "31829401824981a8b94182901a890417bc89410a51982bca8192410a8b941097",
            event_hash: "8249108a71924018941028ba981048190284019af48910481029410a8b918401",
            payload: { reason: feedback, mutations_executed: 0 },
          },
        ];

        return {
          ...t,
          status: "rejected",
          audit_events: updatedEvents,
        };
      })
    );

    setNotification(`Ticket ${ticketId} rejected. Plan terminated with zero mutations.`);
  };

  // Handle Supervisor Edit and Approve
  const handleEditAndApprove = (ticketId: string, editedDraft: string) => {
    setTickets((prev) =>
      prev.map((t) => {
        if (t.ticket_id !== ticketId) return t;
        return {
          ...t,
          status: "completed",
          action_plan: t.action_plan
            ? { ...t.action_plan, reply_draft: editedDraft }
            : undefined,
        };
      })
    );
    setNotification(`Ticket ${ticketId} draft modified and approved! Sent via Mailpit SMTP.`);
  };

  // Handle Topic Re-scan
  const handleRecluster = () => {
    setIsScanning(true);
    setTimeout(() => {
      setIsScanning(false);
      setNotification("Defect topic clustering completed. 3 active clusters indexed.");
    }, 1200);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar />

      {/* Toast Notification */}
      {notification && (
        <div className="fixed bottom-6 right-6 z-50 p-4 rounded-xl bg-slate-900 border border-cyan-500/80 text-cyan-300 text-xs font-mono shadow-2xl flex items-center space-x-2.5 animate-bounce">
          <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>{notification}</span>
        </div>
      )}

      {/* Subheader & Operational Overview */}
      <div className="border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-md px-4 md:px-6 py-3">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-600 to-teal-400 flex items-center justify-center shadow-md shadow-cyan-900/30">
              <Wrench className="w-4 h-4 text-slate-950" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-sm font-bold text-slate-100 tracking-tight">
                  Multi-Agent Ops Copilot (HITL)
                </h1>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-cyan-950 border border-cyan-800 text-cyan-400 font-semibold uppercase">
                  P3 Active
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-mono">
                Presidio PII • XLM-R Multilingual Triage • LangGraph Approvals • SHA-256 Ledger
              </p>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex items-center space-x-1 p-1 bg-slate-900/90 border border-slate-800 rounded-lg text-xs font-mono">
            <button
              onClick={() => setActiveTab("workspace")}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-all ${
                activeTab === "workspace"
                  ? "bg-slate-800 text-cyan-400 shadow-sm border border-slate-700/60 font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Inbox className="w-3.5 h-3.5" />
              <span>Triage & Approvals</span>
              {pendingApprovalsCount > 0 && (
                <span className="px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[9px] font-mono">
                  {pendingApprovalsCount}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab("audit")}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-all ${
                activeTab === "audit"
                  ? "bg-slate-800 text-cyan-400 shadow-sm border border-slate-700/60 font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Audit Ledger</span>
            </button>

            <button
              onClick={() => setActiveTab("insights")}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-all ${
                activeTab === "insights"
                  ? "bg-slate-800 text-cyan-400 shadow-sm border border-slate-700/60 font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Defect Insights</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 overflow-hidden">
        {activeTab === "workspace" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-175px)]">
            {/* Left 4 Cols: Ticket Inbox */}
            <div className="lg:col-span-4 h-full overflow-hidden">
              <TicketInbox
                tickets={tickets}
                selectedTicketId={selectedTicketId}
                onSelectTicket={(t) => setSelectedTicketId(t.ticket_id)}
              />
            </div>

            {/* Right 8 Cols: Ticket Detail Workspace */}
            <div className="lg:col-span-8 h-full overflow-hidden">
              {selectedTicket ? (
                <TicketDetailWorkspace
                  ticket={selectedTicket}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  onEditAndApprove={handleEditAndApprove}
                />
              ) : (
                <div className="h-full flex items-center justify-center border border-slate-800 rounded-xl bg-slate-900/40 text-slate-500 font-mono text-xs">
                  Select a ticket from the inbox to inspect
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "audit" && (
          <div className="h-[calc(100vh-175px)]">
            <AuditLedgerTimeline
              ticketId={selectedTicket.ticket_id}
              events={selectedTicket.audit_events || []}
            />
          </div>
        )}

        {activeTab === "insights" && (
          <div className="h-[calc(100vh-175px)]">
            <DefectInsightsView
              clusters={clusters}
              onRecluster={handleRecluster}
              isScanning={isScanning}
            />
          </div>
        )}
      </main>
    </div>
  );
}
