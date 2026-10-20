"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Truck,
  Scale,
  ShieldAlert,
  Send,
  Sparkles,
  Check,
  X,
  Layers,
  Copy,
  Info,
} from "lucide-react";
import {
  MOCK_DOCAI_DOCUMENTS,
  MOCK_DELIVERY_NOTES,
  MOCK_CONTRACTS,
} from "@/lib/docai-data";

export default function DocumentDetailViewer() {
  const params = useParams();
  const documentId = (params?.id as string) || "DOC-DN-HAM-8921";

  const doc =
    MOCK_DOCAI_DOCUMENTS.find((d) => d.document_id === documentId) ||
    MOCK_DOCAI_DOCUMENTS[0];

  const deliveryNote = MOCK_DELIVERY_NOTES[documentId] || MOCK_DELIVERY_NOTES["DOC-DN-HAM-8921"];
  const contract = MOCK_CONTRACTS[documentId] || MOCK_CONTRACTS["DOC-CTR-WRO-1092"];

  const [activeTab, setActiveTab] = useState<"extraction" | "playbook" | "audit">("extraction");
  const [highlightedField, setHighlightedField] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState<string | null>(null);

  // Editable delivery note state
  const [editedPO, setEditedPO] = useState(deliveryNote.po_number);
  const [editedTotalQty, setEditedTotalQty] = useState(deliveryNote.total_qty);

  const handleIngestToOntology = () => {
    setSuccessToast(`✓ Successfully ingested ${doc.filename} into P1 Halden Ontology!`);
    setTimeout(() => setSuccessToast(null), 4000);
  };

  const isContract = doc.document_type === "contract";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-6 flex flex-col h-screen">
      {/* Top Header Bar */}
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-4 shrink-0">
        <div className="flex items-center gap-3">
          <Link
            href="/docai"
            className="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-slate-100 text-sm md:text-base">{doc.filename}</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-cyan-400">
                {doc.document_id}
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300">
                Plant {doc.plant || "Global"}
              </span>
            </div>
            <div className="text-[11px] text-slate-400 font-mono mt-0.5">
              {doc.document_type.toUpperCase()} • Confidence: {((doc.confidence || 0.95) * 100).toFixed(1)}% •
              Magic bytes: application/pdf
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {successToast && (
            <div className="text-xs font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800 px-3 py-1.5 rounded-lg flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              {successToast}
            </div>
          )}

          <button
            onClick={handleIngestToOntology}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-semibold text-xs shadow-lg shadow-emerald-950/40 transition-all"
          >
            <Check className="w-4 h-4 text-slate-950" />
            Accept & Ingest to Ontology
          </button>
        </div>
      </div>

      {/* Main Split Layout */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 pt-4 overflow-hidden">
        {/* Left Pane: Visual Document Canvas & Bounding Box Overlay (5 cols) */}
        <div className="lg:col-span-5 flex flex-col rounded-xl bg-slate-900/70 border border-slate-800 overflow-hidden">
          <div className="p-3 border-b border-slate-800 bg-slate-950/40 flex items-center justify-between text-xs font-mono text-slate-400">
            <span className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              DOCUMENT CANVAS & BOUNDING BOXES (200 DPI)
            </span>
            <span>Page 1 of {doc.page_count}</span>
          </div>

          <div className="flex-1 p-6 overflow-y-auto flex items-center justify-center bg-slate-950/50">
            {/* Visual Document Mock Page */}
            <div className="w-full max-w-md aspect-[1/1.414] bg-slate-900 rounded-lg border border-slate-700 shadow-2xl p-6 relative flex flex-col justify-between text-slate-300 text-[10px] font-mono leading-relaxed select-none">
              {/* Document Header Box */}
              <div>
                <div
                  onMouseEnter={() => setHighlightedField("supplier")}
                  onMouseLeave={() => setHighlightedField(null)}
                  className={`p-2 rounded border transition-all cursor-pointer ${
                    highlightedField === "supplier"
                      ? "border-cyan-400 bg-cyan-950/60 shadow-lg shadow-cyan-950"
                      : "border-emerald-500/50 bg-emerald-950/20"
                  }`}
                >
                  <div className="font-bold text-slate-100 text-xs">
                    {isContract ? contract.parties[1] : deliveryNote.supplier_name}
                  </div>
                  <div className="text-slate-400 text-[9px] mt-0.5">
                    {isContract ? "Wrocław Plant Direct Supplier" : deliveryNote.supplier_address}
                  </div>
                  <span className="text-[8px] text-emerald-400 uppercase font-semibold">
                    ✓ Verified Grounded Entity (BBox [50, 80, 520, 120])
                  </span>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-2">
                  <div
                    onMouseEnter={() => setHighlightedField("po_number")}
                    onMouseLeave={() => setHighlightedField(null)}
                    className={`p-1.5 rounded border transition-all cursor-pointer ${
                      highlightedField === "po_number"
                        ? "border-cyan-400 bg-cyan-950/60"
                        : "border-emerald-500/50 bg-emerald-950/20"
                    }`}
                  >
                    <div className="text-slate-500 text-[8px]">PO NUMBER / REF</div>
                    <div className="font-semibold text-slate-200 text-[10px]">
                      {isContract ? "CTR-2026-HALDEN" : editedPO}
                    </div>
                  </div>

                  <div
                    onMouseEnter={() => setHighlightedField("date")}
                    onMouseLeave={() => setHighlightedField(null)}
                    className={`p-1.5 rounded border transition-all cursor-pointer ${
                      highlightedField === "date"
                        ? "border-cyan-400 bg-cyan-950/60"
                        : "border-emerald-500/50 bg-emerald-950/20"
                    }`}
                  >
                    <div className="text-slate-500 text-[8px]">DATE</div>
                    <div className="font-semibold text-slate-200 text-[10px]">
                      {isContract ? "2026-10-19" : deliveryNote.delivery_date}
                    </div>
                  </div>
                </div>
              </div>

              {/* Document Middle Body */}
              <div className="my-4 flex-1 flex flex-col justify-center">
                {isContract ? (
                  <div className="space-y-2">
                    <div
                      onMouseEnter={() => setHighlightedField("liability")}
                      onMouseLeave={() => setHighlightedField(null)}
                      className={`p-2 rounded border transition-all cursor-pointer ${
                        highlightedField === "liability"
                          ? "border-rose-400 bg-rose-950/60 shadow-lg shadow-rose-950"
                          : "border-rose-500/60 bg-rose-950/30"
                      }`}
                    >
                      <div className="font-semibold text-rose-300 text-[9px]">
                        § 2.1 Limitation of Aggregate Liability
                      </div>
                      <div className="text-slate-300 text-[9px] line-clamp-2">
                        {contract.clauses[1].text}
                      </div>
                      <span className="text-[8px] text-rose-400 font-bold uppercase block mt-1">
                        ⚠ PLAYBOOK VIOLATION: Cap 5.0x exceeds 2.0x limit
                      </span>
                    </div>

                    <div
                      onMouseEnter={() => setHighlightedField("governing_law")}
                      onMouseLeave={() => setHighlightedField(null)}
                      className={`p-2 rounded border transition-all cursor-pointer ${
                        highlightedField === "governing_law"
                          ? "border-amber-400 bg-amber-950/60 shadow-lg shadow-amber-950"
                          : "border-amber-500/60 bg-amber-950/30"
                      }`}
                    >
                      <div className="font-semibold text-amber-300 text-[9px]">
                        § 3.1 Governing Law and Jurisdiction
                      </div>
                      <div className="text-slate-300 text-[9px] line-clamp-2">
                        {contract.clauses[2].text}
                      </div>
                      <span className="text-[8px] text-amber-400 font-bold uppercase block mt-1">
                        ⚠ NON-COMPLIANT: Foreign Law (State of New York)
                      </span>
                    </div>
                  </div>
                ) : (
                  <div
                    onMouseEnter={() => setHighlightedField("line_items")}
                    onMouseLeave={() => setHighlightedField(null)}
                    className={`p-2 rounded border transition-all cursor-pointer ${
                      highlightedField === "line_items"
                        ? "border-cyan-400 bg-cyan-950/60"
                        : deliveryNote.validators.SUM_QUANTITIES_MATCH.status === "FAIL"
                        ? "border-amber-500/80 bg-amber-950/30"
                        : "border-emerald-500/50 bg-emerald-950/20"
                    }`}
                  >
                    <div className="text-[9px] font-bold text-slate-200 border-b border-slate-700 pb-1 mb-1">
                      LINE ITEMS TABLE (DONUT PARSED)
                    </div>
                    {deliveryNote.line_items.map((item, idx) => (
                      <div key={idx} className="flex justify-between py-0.5 text-[8.5px]">
                        <span>{item.part_no}</span>
                        <span>{item.qty} {item.unit}</span>
                      </div>
                    ))}
                    <div className="border-t border-slate-700 mt-1 pt-1 flex justify-between font-bold text-slate-100">
                      <span>TOTAL QUANTITY:</span>
                      <span>{deliveryNote.total_qty}</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Document Footer Barcode & Watermark */}
              <div className="border-t border-slate-800 pt-2 flex items-center justify-between text-[8px] text-slate-500 font-mono">
                <span>SHA-256: 4f8a91c0e3...</span>
                <span>HALDEN INTAKE VERIFIED</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Pane: Structured Intelligence & Human-in-the-Loop Review (7 cols) */}
        <div className="lg:col-span-7 flex flex-col rounded-xl bg-slate-900/70 border border-slate-800 overflow-hidden">
          {/* Navigation Sub-Tabs */}
          <div className="p-2 border-b border-slate-800 bg-slate-950/40 flex items-center space-x-1">
            <button
              onClick={() => setActiveTab("extraction")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeTab === "extraction"
                  ? "bg-slate-800 text-cyan-400 shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Extracted Entities & Invariants
            </button>

            {isContract && (
              <button
                onClick={() => setActiveTab("playbook")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === "playbook"
                    ? "bg-slate-800 text-cyan-400 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                Playbook Compliance ({contract.playbook_findings.filter((f) => f.status === "FAIL").length} Violations)
              </button>
            )}

            <button
              onClick={() => setActiveTab("audit")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeTab === "audit"
                  ? "bg-slate-800 text-cyan-400 shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Audit Pipeline Timeline
            </button>
          </div>

          {/* Right Pane Body */}
          <div className="flex-1 p-6 overflow-y-auto space-y-6">
            {activeTab === "extraction" && (
              <div className="space-y-6">
                {isContract ? (
                  /* Contract Clauses Breakdown */
                  <div className="space-y-4">
                    <h2 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider">
                      SEGMENTED & SPAN-GROUNDED CLAUSES (CUAD CLASSIFIED)
                    </h2>
                    {contract.clauses.map((clause) => (
                      <div
                        key={clause.clause_id}
                        className="p-4 rounded-xl bg-slate-950/50 border border-slate-800 hover:border-slate-700 transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-200 text-xs">
                            {clause.section_number} {clause.title}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800">
                            ✓ 100% Span Grounded [chars {clause.char_start}..{clause.char_end}]
                          </span>
                        </div>
                        <p className="text-xs text-slate-300 mt-2 leading-relaxed bg-slate-900/50 p-2.5 rounded-lg font-mono">
                          {clause.text}
                        </p>
                        {clause.categories.length > 0 && (
                          <div className="mt-2.5 flex flex-wrap gap-1.5">
                            {clause.categories.map((cat) => (
                              <span
                                key={cat}
                                className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-800"
                              >
                                {cat} ({((clause.category_scores[cat] || 0.9) * 100).toFixed(0)}%)
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  /* Delivery Note Extraction Form & Validation */
                  <div className="space-y-6">
                    <div>
                      <h2 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider mb-3">
                        HEADER FIELDS (HUMAN-IN-THE-LOOP CORRECTION)
                      </h2>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <label className="text-[11px] font-mono text-slate-400">Supplier Name</label>
                          <input
                            type="text"
                            defaultValue={deliveryNote.supplier_name}
                            className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[11px] font-mono text-slate-400">PO Number</label>
                          <input
                            type="text"
                            value={editedPO}
                            onChange={(e) => setEditedPO(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[11px] font-mono text-slate-400">Delivery Date</label>
                          <input
                            type="text"
                            defaultValue={deliveryNote.delivery_date}
                            className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[11px] font-mono text-slate-400">Total Quantity</label>
                          <input
                            type="number"
                            value={editedTotalQty}
                            onChange={(e) => setEditedTotalQty(Number(e.target.value))}
                            className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Deterministic Business Validators */}
                    <div>
                      <h2 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider mb-3">
                        ERP & ONTOLOGY DETERMINISTIC VALIDATORS
                      </h2>
                      <div className="space-y-2">
                        {Object.entries(deliveryNote.validators).map(([ruleName, rule]) => (
                          <div
                            key={ruleName}
                            className={`p-3 rounded-xl border flex items-start gap-3 ${
                              rule.status === "PASS"
                                ? "bg-emerald-950/20 border-emerald-800/60 text-emerald-300"
                                : "bg-rose-950/20 border-rose-800/60 text-rose-300"
                            }`}
                          >
                            {rule.status === "PASS" ? (
                              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                            ) : (
                              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                            )}
                            <div>
                              <div className="text-xs font-mono font-bold">{ruleName}</div>
                              <div className="text-[11px] text-slate-300 mt-0.5">{rule.message}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === "playbook" && isContract && (
              /* Sofia Schmidt Legal Playbook Auditing */
              <div className="space-y-4">
                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs">
                  <div>
                    <span className="font-bold text-slate-200">Playbook: halden_v1.yaml</span>
                    <span className="text-slate-400 block text-[11px]">
                      Enforcing strict liability caps, German governing law, and 90-day renewal terms.
                    </span>
                  </div>
                  <span className="px-2.5 py-1 rounded bg-rose-950 border border-rose-800 text-rose-300 text-xs font-mono font-bold">
                    3 Non-Compliant Risks
                  </span>
                </div>

                <div className="space-y-3">
                  {contract.playbook_findings.map((finding) => (
                    <div
                      key={finding.rule_id}
                      className={`p-4 rounded-xl border space-y-2 ${
                        finding.status === "FAIL"
                          ? "bg-rose-950/20 border-rose-800/80"
                          : "bg-emerald-950/20 border-emerald-800/60"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs text-slate-100 flex items-center gap-2">
                          {finding.status === "FAIL" ? (
                            <ShieldAlert className="w-4 h-4 text-rose-400" />
                          ) : (
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                          )}
                          {finding.rule_name}
                        </span>
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                            finding.severity === "CRITICAL"
                              ? "bg-rose-950 text-rose-400 border border-rose-800"
                              : finding.severity === "HIGH"
                              ? "bg-amber-950 text-amber-300 border border-amber-800"
                              : "bg-slate-800 text-slate-300"
                          }`}
                        >
                          {finding.severity}
                        </span>
                      </div>

                      <p className="text-xs text-slate-300">{finding.message}</p>

                      {finding.fallback_recommendation && (
                        <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                          <div className="flex items-center justify-between text-[10px] font-mono text-cyan-400">
                            <span>RECOMMENDED SOFIA SCHMIDT FALLBACK CLAUSE:</span>
                            <button
                              onClick={() => {
                                navigator.clipboard.writeText(finding.fallback_recommendation || "");
                                alert("Copied fallback clause to clipboard!");
                              }}
                              className="flex items-center gap-1 hover:text-cyan-300"
                            >
                              <Copy className="w-3 h-3" />
                              Copy
                            </button>
                          </div>
                          <p className="text-xs text-slate-300 font-mono leading-relaxed">
                            {finding.fallback_recommendation}
                          </p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "audit" && (
              /* Execution Steps Timeline */
              <div className="space-y-4">
                <h2 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider">
                  AUDITED EXECUTION PIPELINE STEPS
                </h2>
                <div className="space-y-2.5 font-mono text-xs">
                  {[
                    { step: "MAGIC_BYTE_VALIDATION", duration: "1.2 ms", status: "PASS", detail: "application/pdf verified" },
                    { step: "PAGE_PREPROCESSING", duration: "18.4 ms", status: "PASS", detail: "200 DPI rendered, deskew residual 0.08°" },
                    { step: "OCR_TESSERACT_HYBRID", duration: "124.0 ms", status: "PASS", detail: "Native PyMuPDF text layer detected" },
                    { step: "DONUT_FIELD_EXTRACTION", duration: "3.6 ms", status: "PASS", detail: "Confidence 0.985" },
                    { step: "DETERMINISTIC_BUSINESS_VALIDATORS", duration: "0.2 ms", status: "PASS", detail: "6/6 rules evaluated" },
                    { step: "ONTOLOGY_STAGE_PREPARED", duration: "4.1 ms", status: "READY", detail: "Ready for publication" },
                  ].map((s, i) => (
                    <div
                      key={i}
                      className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2.5">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        <div>
                          <div className="font-bold text-slate-200">{s.step}</div>
                          <div className="text-[11px] text-slate-500 font-sans">{s.detail}</div>
                        </div>
                      </div>
                      <span className="text-[11px] text-cyan-400">{s.duration}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
