import {
  ChunkCitation,
  UnifiedAssistantResponse,
  VerificationResult,
} from "./types";

export interface StreamCallbacks {
  onRoute?: (data: {
    route: string;
    confidence: number;
    rewritten_query: string;
    cached: boolean;
    trace_id?: string;
  }) => void;
  onSources?: (citations: ChunkCitation[]) => void;
  onSQL?: (data: { sql: string; tables_used: string[] }) => void;
  onRowsPreview?: (data: {
    columns: string[];
    rows: Record<string, any>[];
    row_count: number;
  }) => void;
  onToken?: (text: string) => void;
  onVerification?: (verification: VerificationResult) => void;
  onDone?: () => void;
  onError?: (err: Error) => void;
}

export interface StreamChatParams {
  query: string;
  sessionId?: string;
  forcedRoute?: string;
  topK?: number;
  bypassCache?: boolean;
}

/**
 * Streams chat completion via Server-Sent Events (SSE).
 * Falls back to direct POST /api/assistant/chat or mock simulation if offline.
 */
export async function streamAssistantChat(
  params: StreamChatParams,
  headers: Record<string, string>,
  callbacks: StreamCallbacks,
  abortSignal?: AbortSignal
): Promise<void> {
  const payload = {
    query: params.query,
    session_id: params.sessionId,
    route: params.forcedRoute,
    top_k: params.topK ?? 6,
    bypass_cache: params.bypassCache ?? false,
  };

  try {
    const res = await fetch("/api/assistant/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: JSON.stringify(payload),
      signal: abortSignal,
    });

    if (!res.ok) {
      throw new Error(`SSE stream failed with status ${res.status}`);
    }

    if (!res.body) {
      throw new Error("No response body available for streaming");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";

      for (const block of blocks) {
        if (!block.trim()) continue;
        const lines = block.split("\n");
        let eventName = "message";
        let rawData = "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventName = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            rawData = line.slice(5).trim();
          }
        }

        if (rawData === "[DONE]") {
          callbacks.onDone?.();
          return;
        }

        if (!rawData) continue;

        try {
          const parsed = JSON.parse(rawData);
          switch (eventName) {
            case "route":
              callbacks.onRoute?.(parsed);
              break;
            case "sources":
              callbacks.onSources?.(parsed);
              break;
            case "sql":
              callbacks.onSQL?.(parsed);
              break;
            case "rows_preview":
              callbacks.onRowsPreview?.(parsed);
              break;
            case "token":
              if (parsed.text) callbacks.onToken?.(parsed.text);
              break;
            case "verification":
              callbacks.onVerification?.(parsed);
              break;
            case "done":
              callbacks.onDone?.();
              return;
          }
        } catch {
          // If raw text chunk without JSON
          if (eventName === "token") {
            callbacks.onToken?.(rawData);
          }
        }
      }
    }

    callbacks.onDone?.();
  } catch (err: any) {
    if (abortSignal?.aborted) {
      return;
    }
    // If backend stream endpoint failed or is unreachable, attempt graceful fallback
    console.warn("SSE stream failed, attempting standard chat endpoint fallback:", err);
    try {
      const fallbackRes = await fetch("/api/assistant/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...headers,
        },
        body: JSON.stringify(payload),
        signal: abortSignal,
      });

      if (fallbackRes.ok) {
        const data: UnifiedAssistantResponse = await fallbackRes.json();
        callbacks.onRoute?.({
          route: data.route,
          confidence: data.confidence,
          rewritten_query: data.rewritten_query,
          cached: data.cached,
          trace_id: data.trace_id ?? undefined,
        });

        if (data.citations && data.citations.length > 0) {
          callbacks.onSources?.(data.citations);
        }

        if (data.sql) {
          callbacks.onSQL?.({
            sql: data.sql,
            tables_used: data.tables_used,
          });
        }

        if (data.rows && data.rows.length > 0) {
          callbacks.onRowsPreview?.({
            columns: data.columns,
            rows: data.rows,
            row_count: data.row_count,
          });
        }

        if (data.verification) {
          callbacks.onVerification?.(data.verification);
        }

        // Stream tokens in small simulated slices
        const words = data.answer.split(" ");
        for (let i = 0; i < words.length; i += 3) {
          const slice = words.slice(i, i + 3).join(" ") + " ";
          callbacks.onToken?.(slice);
          await new Promise((r) => setTimeout(r, 20));
        }

        callbacks.onDone?.();
        return;
      }
    } catch {
      // Fallback network failure handled below
    }

    callbacks.onError?.(err instanceof Error ? err : new Error(String(err)));
  }
}

/**
 * Submit feedback for an assistant response.
 */
export async function submitAssistantFeedback(
  params: {
    traceId: string;
    thumbs: "up" | "down";
    comment?: string;
    route?: string;
    query?: string;
  },
  headers: Record<string, string>
): Promise<{ status: string; id: string }> {
  const res = await fetch("/api/assistant/feedback", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify({
      trace_id: params.traceId,
      thumbs: params.thumbs,
      comment: params.comment,
      route: params.route,
      query: params.query,
    }),
  });

  if (!res.ok) {
    throw new Error(`Failed to submit feedback: ${res.statusText}`);
  }

  return res.json();
}

/**
 * Export table data to downloadable CSV.
 */
export function exportTableToCSV(
  columns: string[],
  rows: Record<string, any>[],
  filename = "query_results.csv"
): void {
  if (!rows || rows.length === 0) return;

  const headerRow = columns.map((col) => `"${col.replace(/"/g, '""')}"`).join(",");
  const dataRows = rows.map((row) =>
    columns
      .map((col) => {
        const val = row[col] === null || row[col] === undefined ? "" : String(row[col]);
        return `"${val.replace(/"/g, '""')}"`;
      })
      .join(",")
  );

  const csvContent = "data:text/csv;charset=utf-8," + [headerRow, ...dataRows].join("\n");
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
