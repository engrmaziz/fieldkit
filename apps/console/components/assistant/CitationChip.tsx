"use client";

import React from "react";
import { BookOpen } from "lucide-react";

interface CitationChipProps {
  index: number;
  title?: string;
  onClick: (index: number) => void;
}

export default function CitationChip({
  index,
  title,
  onClick,
}: CitationChipProps) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick(index);
      }}
      className="inline-flex items-center space-x-1 px-1.5 py-0.5 mx-0.5 rounded text-[11px] font-mono font-bold bg-teal-950/80 text-teal-300 border border-teal-700/60 hover:bg-teal-900 hover:border-teal-400 hover:text-white transition-all transform hover:scale-105 active:scale-95 shadow-sm"
      title={title ? `View Citation [${index}]: ${title}` : `View Citation [${index}]`}
    >
      <BookOpen className="w-3 h-3 text-teal-400" />
      <span>[{index}]</span>
    </button>
  );
}
