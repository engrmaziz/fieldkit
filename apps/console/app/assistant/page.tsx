"use client";

import React, { useState, useRef, useEffect } from "react";
import { useAuth, DEMO_USERS } from "@/lib/auth-context";
import {
  ChatMessage,
  ChunkCitation,
  UnifiedAssistantResponse,
  VerificationResult,
} from "@/lib/types";
import { streamAssistantChat } from "@/lib/assistant-api";
import PersonaBar from "@/components/assistant/PersonaBar";
import RouteBadge from "@/components/assistant/RouteBadge";
import CitationChip from "@/components/assistant/CitationChip";
import CitationDrawer from "@/components/assistant/CitationDrawer";
import SQLBlock from "@/components/assistant/SQLBlock";
import AclRefusalBanner from "@/components/assistant/AclRefusalBanner";
import FeedbackButtons from "@/components/assistant/FeedbackButtons";
import {
  Bot,
  Send,
  Sparkles,
  RotateCcw,
  ShieldCheck,
  AlertTriangle,
  Layers,
  StopCircle,
  HelpCircle,
  Clock,
  BookOpen,
} from "lucide-react";

export default function AssistantPage() {
  const { currentUser, setUser, getAuthHeaders } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputQuery, setInputQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedRoute, setSelectedRoute] = useState<string>("auto");
  const [selectedCitation, setSelectedCitation] = useState<ChunkCitation | null>(
    null
  );
  const [drawerOpen, setDrawerOpen] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const chatBottomRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleCitationClick = (
    citationIndex: number,
    citationsList?: ChunkCitation[]
  ) => {
    if (!citationsList || citationsList.length === 0) return;
    const found = citationsList.find((c) => c.citation_index === citationIndex);
    if (found) {
      setSelectedCitation(found);
      setDrawerOpen(true);
    }
  };

  const handleStopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.isStreaming) {
          return [
            ...prev.slice(0, -1),
            { ...last, isStreaming: false, content: last.content + " [Streaming stopped]" },
          ];
        }
        return prev;
      });
    }
  };

  const handleSendMessage = async (queryToSend?: string) => {
    const text = (queryToSend || inputQuery).trim();
    if (!text || isLoading) return;

    setInputQuery("");

    const userMessageId = `user-${Date.now()}`;
    const assistantMessageId = `assistant-${Date.now()}`;

    const userMsg: ChatMessage = {
      id: userMessageId,
      sender: "user",
      content: text,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    const initialAssistantMsg: ChatMessage = {
      id: assistantMessageId,
      sender: "assistant",
      content: "",
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
      isStreaming: true,
      citations: [],
    };

    setMessages((prev) => [...prev, userMsg, initialAssistantMsg]);
    setIsLoading(true);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const forcedRouteParam = selectedRoute === "auto" ? undefined : selectedRoute;

    await streamAssistantChat(
      {
        query: text,
        sessionId: `session-${currentUser.username}`,
        forcedRoute: forcedRouteParam,
        topK: 6,
      },
      getAuthHeaders(),
      {
        onRoute: (routeData) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    route: routeData.route,
                    confidence: routeData.confidence,
                    rewritten_query: routeData.rewritten_query,
                    cached: routeData.cached,
                    trace_id: routeData.trace_id,
                  }
                : msg
            )
          );
        },
        onSources: (citations) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    citations: citations,
                  }
                : msg
            )
          );
        },
        onSQL: (sqlData) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    sql: sqlData.sql,
                    tables_used: sqlData.tables_used,
                  }
                : msg
            )
          );
        },
        onRowsPreview: (previewData) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    columns: previewData.columns,
                    rows: previewData.rows,
                    row_count: previewData.row_count,
                  }
                : msg
            )
          );
        },
        onToken: (token) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content: msg.content + token,
                  }
                : msg
            )
          );
        },
        onVerification: (verification) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    verification: verification,
                  }
                : msg
            )
          );
        },
        onDone: () => {
          setIsLoading(false);
          abortControllerRef.current = null;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    isStreaming: false,
                  }
                : msg
            )
          );
        },
        onError: (err) => {
          setIsLoading(false);
          abortControllerRef.current = null;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    isStreaming: false,
                    content:
                      msg.content ||
                      `Error communicating with Fieldkit Assistant service: ${err.message}`,
                  }
                : msg
            )
          );
        },
      },
      abortController.signal
    );
  };

  const handleClearChat = () => {
    setMessages([]);
  };

  const handleSwitchToSofiaAndRetry = (originalQuery: string) => {
    const sofia = DEMO_USERS.find((u) => u.username === "sofia");
    if (sofia) {
      setUser(sofia);
      setTimeout(() => {
        handleSendMessage(originalQuery);
      }, 200);
    }
  };

  // Helper to parse answer string with bracketed citations [1], [2], [1, 2]
  const renderFormattedAnswer = (
    text: string,
    citationsList?: ChunkCitation[]
  ) => {
    if (!text) return null;

    // Regex to split by citation patterns like [1] or [1, 2]
    const parts = text.split(/(\[\d+(?:,\s*\d+)*\])/g);

    return parts.map((part, idx) => {
      const match = part.match(/^\[(\d+(?:,\s*\d+)*)\]$/);
      if (match) {
        const indices = match[1].split(",").map((s) => parseInt(s.trim(), 10));
        return (
          <span key={idx} className="inline-flex items-center">
            {indices.map((cIdx) => {
              const citObj = citationsList?.find(
                (c) => c.citation_index === cIdx
              );
              return (
                <CitationChip
                  key={cIdx}
                  index={cIdx}
                  title={citObj?.title}
                  onClick={() => handleCitationClick(cIdx, citationsList)}
                />
              );
            })}
          </span>
        );
      }
      return <span key={idx}>{part}</span>;
    });
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800/80 gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-cyan-600/20 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
              <Bot className="w-5 h-5" />
            </div>
            <span>Fieldkit Operations Assistant</span>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-800 text-cyan-400 font-semibold">
              P2 RAG + NL2SQL
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Hybrid enterprise assistant executing local RAG, deterministic grounding verification, and AST-validated NL2SQL.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {messages.length > 0 && (
            <button
              type="button"
              onClick={handleClearChat}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 bg-slate-900 border border-slate-800 hover:bg-slate-800 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset Chat</span>
            </button>
          )}
        </div>
      </div>

      {/* Persona Bar & Benchmark Prompts */}
      <PersonaBar onSelectPrompt={(prompt) => handleSendMessage(prompt)} />

      {/* Chat Messages Transcript */}
      <div className="space-y-6 min-h-[350px]">
        {messages.length === 0 ? (
          /* Welcome Banner */
          <div className="p-8 rounded-2xl bg-slate-900/40 border border-slate-800/80 text-center space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 flex items-center justify-center mx-auto shadow-lg shadow-cyan-950/40">
              <Sparkles className="w-6 h-6" />
            </div>
            <div className="max-w-md mx-auto space-y-2">
              <h3 className="text-base font-bold text-white">
                Halden Industrie Operational Copilot
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Ask about manufacturing SOPs, surface tolerances, plant incident logs, or operational metrics like purchase order volumes and supplier delivery status.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-2xl mx-auto pt-2 text-left">
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs space-y-1">
                <span className="text-[10px] font-mono text-emerald-400 uppercase font-semibold block">
                  1. RAG Retrieval
                </span>
                <p className="text-slate-300">
                  Hybrid BM25 + dense vector search with chunk-level ACL pre-filtering.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs space-y-1">
                <span className="text-[10px] font-mono text-cyan-400 uppercase font-semibold block">
                  2. NL2SQL Engine
                </span>
                <p className="text-slate-300">
                  SQLGlot AST validation blocking mutations with read-only execution.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs space-y-1">
                <span className="text-[10px] font-mono text-purple-400 uppercase font-semibold block">
                  3. Hybrid Synthesis
                </span>
                <p className="text-slate-300">
                  Combines tabular SQL statistics with authoritative regulatory clauses.
                </p>
              </div>
            </div>
          </div>
        ) : (
          /* Render Messages */
          messages.map((msg) => (
            <div key={msg.id} className="space-y-2">
              {msg.sender === "user" ? (
                /* User Message Bubble */
                <div className="flex items-start justify-end space-x-3">
                  <div className="max-w-2xl rounded-2xl rounded-tr-sm bg-gradient-to-r from-cyan-600 to-teal-600 p-4 text-white shadow-lg text-sm leading-relaxed">
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                    <span className="text-[10px] opacity-75 font-mono block text-right mt-1.5">
                      {msg.timestamp}
                    </span>
                  </div>
                </div>
              ) : (
                /* Assistant Message Card */
                <div className="glass-panel rounded-2xl p-5 border border-slate-800 shadow-xl space-y-4">
                  {/* Top Bar: Route Badge & Latency/Cache Status */}
                  <div className="flex items-center justify-between border-b border-slate-800/60 pb-3">
                    <div className="flex items-center space-x-2">
                      <div className="w-7 h-7 rounded-lg bg-cyan-600/20 border border-cyan-500/30 flex items-center justify-center text-cyan-300 text-xs">
                        <Bot className="w-4 h-4" />
                      </div>
                      <span className="text-xs font-bold text-white tracking-wide">
                        Fieldkit Assistant
                      </span>
                    </div>

                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] font-mono text-slate-500 flex items-center space-x-1">
                        <Clock className="w-3 h-3" />
                        <span>{msg.timestamp}</span>
                      </span>
                    </div>
                  </div>

                  {/* Dynamic Route Pill */}
                  <RouteBadge
                    route={msg.route}
                    confidence={msg.confidence}
                    cached={msg.cached}
                    rewrittenQuery={msg.rewritten_query}
                  />

                  {/* Main Answer Text */}
                  <div className="text-sm text-slate-200 leading-relaxed font-sans selection:bg-cyan-500/30 selection:text-cyan-200 whitespace-pre-wrap">
                    {renderFormattedAnswer(msg.content, msg.citations)}
                    {msg.isStreaming && (
                      <span className="inline-block w-2 h-4 ml-1 bg-cyan-400 animate-pulse align-middle" />
                    )}
                  </div>

                  {/* Grounding Verification Telemetry */}
                  {msg.verification && (
                    <div className="flex items-center space-x-2 p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs">
                      {msg.verification.is_supported ? (
                        <>
                          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                          <span className="text-emerald-300 font-mono text-[11px]">
                            Deterministic Grounding Verified (
                            {Math.round(msg.verification.supported_ratio * 100)}% sentence support)
                          </span>
                        </>
                      ) : (
                        <>
                          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                          <span className="text-amber-300 font-mono text-[11px]">
                            Grounding Telemetry: {msg.verification.unsupported_count} unsupported sentences flagged
                          </span>
                        </>
                      )}
                    </div>
                  )}

                  {/* Collapsible SQL Block & Virtualized Table Preview */}
                  {msg.sql && (
                    <SQLBlock
                      sql={msg.sql}
                      tablesUsed={msg.tables_used}
                      columns={msg.columns}
                      rows={msg.rows}
                      rowCount={msg.row_count}
                    />
                  )}

                  {/* Citation Sources Chips Bottom Strip */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="p-3 rounded-xl bg-slate-900/40 border border-slate-800/80 space-y-2">
                      <div className="flex items-center space-x-1.5 text-[11px] font-mono text-slate-400 font-semibold uppercase tracking-wider">
                        <BookOpen className="w-3.5 h-3.5 text-teal-400" />
                        <span>Authoritative Sources Cited ({msg.citations.length}):</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {msg.citations.map((c) => (
                          <button
                            key={c.citation_index}
                            type="button"
                            onClick={() => {
                              setSelectedCitation(c);
                              setDrawerOpen(true);
                            }}
                            className="flex items-center space-x-2 px-2.5 py-1.5 rounded-lg text-xs bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-teal-500/50 text-slate-300 hover:text-white transition-all text-left"
                          >
                            <span className="w-5 h-5 rounded bg-teal-950 border border-teal-700/60 text-teal-300 font-mono font-bold flex items-center justify-center text-[10px]">
                              [{c.citation_index}]
                            </span>
                            <span className="font-medium truncate max-w-xs">
                              {c.title}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* "Why can't I see this?" ACL Refusal Accordion */}
                  <AclRefusalBanner
                    content={msg.content}
                    currentUser={currentUser}
                    onSwitchToAdminAndRetry={() => {
                      const userQuery = messages
                        .slice(0, messages.indexOf(msg))
                        .reverse()
                        .find((m) => m.sender === "user")?.content;
                      if (userQuery) {
                        handleSwitchToSofiaAndRetry(userQuery);
                      }
                    }}
                  />

                  {/* Inline Thumbs Up / Down Feedback & OpenTelemetry Trace */}
                  {!msg.isStreaming && msg.content && (
                    <FeedbackButtons
                      traceId={msg.trace_id}
                      route={msg.route}
                      query={
                        messages
                          .slice(0, messages.indexOf(msg))
                          .reverse()
                          .find((m) => m.sender === "user")?.content
                      }
                    />
                  )}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={chatBottomRef} />
      </div>

      {/* Floating Chat Input Bar */}
      <div className="sticky bottom-4 z-40">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="glass-panel p-2.5 rounded-2xl border border-slate-800/90 shadow-2xl bg-slate-950/90 backdrop-blur-xl space-y-2"
        >
          {/* Controls Bar: Route Override */}
          <div className="flex items-center justify-between px-2 text-[11px] font-mono text-slate-400">
            <div className="flex items-center space-x-2">
              <span>Routing Override:</span>
              <select
                value={selectedRoute}
                onChange={(e) => setSelectedRoute(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded px-2 py-0.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500/50 font-mono"
              >
                <option value="auto">Auto (Hybrid Router)</option>
                <option value="rag">Force RAG</option>
                <option value="sql">Force NL2SQL</option>
                <option value="both">Force Both (Hybrid)</option>
              </select>
            </div>

            <div className="hidden sm:flex items-center space-x-1.5 text-slate-500">
              <kbd className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px]">
                Enter
              </kbd>
              <span>to send</span>
              <span className="mx-1">•</span>
              <kbd className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px]">
                Shift + Enter
              </kbd>
              <span>newline</span>
            </div>
          </div>

          {/* Text Input Row */}
          <div className="flex items-end space-x-2">
            <textarea
              ref={textareaRef}
              rows={2}
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              placeholder={`Ask a question as ${currentUser.name} (${currentUser.roles.join(", ")})...`}
              className="w-full bg-slate-900/60 border border-slate-800/80 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/30 resize-none transition-all"
            />

            {isLoading ? (
              <button
                type="button"
                onClick={handleStopStreaming}
                className="p-3 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-medium transition-colors flex items-center justify-center shrink-0 shadow-lg shadow-rose-950/40"
                title="Stop streaming"
              >
                <StopCircle className="w-5 h-5" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!inputQuery.trim()}
                className="p-3 rounded-xl bg-gradient-to-r from-cyan-600 to-teal-500 hover:from-cyan-500 hover:to-teal-400 disabled:opacity-40 disabled:cursor-not-allowed text-slate-950 font-bold transition-all flex items-center justify-center shrink-0 shadow-lg shadow-cyan-950/40"
                title="Send query"
              >
                <Send className="w-5 h-5" />
              </button>
            )}
          </div>
        </form>
      </div>

      {/* Slide-over Citation Drawer */}
      <CitationDrawer
        citation={selectedCitation}
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
