"use client";

import React, { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Database,
  Copy,
  Check,
  Download,
  Table as TableIcon,
} from "lucide-react";
import { exportTableToCSV } from "@/lib/assistant-api";

interface SQLBlockProps {
  sql?: string | null;
  tablesUsed?: string[];
  columns?: string[];
  rows?: Record<string, any>[];
  rowCount?: number;
}

export default function SQLBlock({
  sql,
  tablesUsed = [],
  columns = [],
  rows = [],
  rowCount,
}: SQLBlockProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [copied, setCopied] = useState(false);

  if (!sql && (!rows || rows.length === 0)) return null;

  const totalRows = rowCount !== undefined ? rowCount : rows.length;

  const handleCopy = () => {
    if (!sql) return;
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExportCSV = () => {
    if (!columns || columns.length === 0 || !rows || rows.length === 0) return;
    exportTableToCSV(columns, rows, `sql_results_${Date.now()}.csv`);
  };

  return (
    <div className="mt-4 border border-slate-800 rounded-xl bg-slate-950/60 overflow-hidden shadow-lg">
      {/* Header Bar */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        className="px-4 py-3 bg-slate-900/70 border-b border-slate-800/80 flex items-center justify-between cursor-pointer hover:bg-slate-900 transition-colors select-none"
      >
        <div className="flex items-center space-x-2.5">
          {isOpen ? (
            <ChevronDown className="w-4 h-4 text-cyan-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-slate-400" />
          )}
          <Database className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-semibold text-slate-200 tracking-wide">
            NL2SQL Execution & Data Preview
          </span>

          {/* Tables used */}
          {tablesUsed.length > 0 && (
            <div className="hidden sm:flex items-center space-x-1 pl-2">
              {tablesUsed.map((tbl) => (
                <span
                  key={tbl}
                  className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-cyan-950/60 border border-cyan-800/60 text-cyan-300"
                >
                  {tbl}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center space-x-2">
          {totalRows > 0 && (
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 border border-slate-700 text-slate-300">
              {totalRows} {totalRows === 1 ? "row" : "rows"}
            </span>
          )}
        </div>
      </div>

      {isOpen && (
        <div className="p-4 space-y-4">
          {/* SQL Query Display */}
          {sql && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                <span>Deterministic AST-Validated SQL</span>
                <button
                  type="button"
                  onClick={handleCopy}
                  className="flex items-center space-x-1 px-2 py-1 rounded bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white transition-colors"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-400" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3 text-slate-400" />
                      <span>Copy SQL</span>
                    </>
                  )}
                </button>
              </div>

              <pre className="p-3.5 rounded-lg bg-slate-950 border border-slate-800/90 text-cyan-200 text-xs font-mono overflow-x-auto leading-relaxed shadow-inner">
                <code>{sql}</code>
              </pre>
            </div>
          )}

          {/* Result Table Preview */}
          {columns && columns.length > 0 && rows && rows.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-300">
                  <TableIcon className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Execution Result Table</span>
                  <span className="text-[11px] font-normal text-slate-400">
                    (Showing top {rows.length} rows)
                  </span>
                </div>

                <button
                  type="button"
                  onClick={handleExportCSV}
                  className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-cyan-950/60 border border-cyan-800/60 text-cyan-300 hover:bg-cyan-900/80 hover:text-white transition-all shadow-sm"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Export CSV</span>
                </button>
              </div>

              <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 max-h-72">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="sticky top-0 bg-slate-900 border-b border-slate-800 text-slate-300 text-[11px] font-semibold tracking-wider">
                    <tr>
                      {columns.map((col) => (
                        <th key={col} className="px-3.5 py-2 whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {rows.map((row, rIdx) => (
                      <tr
                        key={rIdx}
                        className="hover:bg-slate-900/50 transition-colors"
                      >
                        {columns.map((col) => {
                          const val = row[col];
                          const displayVal =
                            val === null || val === undefined
                              ? "NULL"
                              : String(val);
                          const isNull = val === null || val === undefined;
                          return (
                            <td
                              key={col}
                              className={`px-3.5 py-2 whitespace-nowrap ${
                                isNull ? "text-slate-600 italic" : "text-slate-200"
                              }`}
                            >
                              {displayVal}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
