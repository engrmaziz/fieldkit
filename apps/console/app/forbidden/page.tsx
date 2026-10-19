import Link from "next/link";
import { ShieldAlert, ArrowLeft } from "lucide-react";

export default function ForbiddenPage() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center p-6 space-y-4">
      <div className="w-14 h-14 rounded-2xl bg-rose-950/80 border border-rose-800 text-rose-400 flex items-center justify-center shadow-xl">
        <ShieldAlert className="w-7 h-7" />
      </div>
      <h1 className="text-xl font-bold text-white">403 — Authorization Denied</h1>
      <p className="text-xs text-slate-400 max-w-md leading-relaxed">
        Your current user roles or plant credentials restrict access to this resource under Halden Industrie
        Row-Level Security (RLS) policies. Please switch persona via the top right switcher to test alternative role permissions.
      </p>
      <Link
        href="/foundry/explorer"
        className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium inline-flex items-center space-x-2 transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Return to Foundry Explorer</span>
      </Link>
    </div>
  );
}
