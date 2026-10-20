"""Asynchronous, idempotent worker executing document processing steps."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pymupdf
from fieldkit_common.logging import get_logger

from fieldkit_docai.models import (
    DocumentRecord,
    DocumentStatus,
    PageResult,
    StepStatus,
)
from fieldkit_docai.pipeline.classify import classify_document_type
from fieldkit_docai.pipeline.layout import segment_page_layout
from fieldkit_docai.pipeline.ocr import extract_page_text_and_boxes
from fieldkit_docai.pipeline.preprocess import (
    denoise_image,
    deskew_image,
    render_image_bytes,
    render_pdf_pages_to_images,
)
from fieldkit_docai.storage import DocumentStore

logger = get_logger("fieldkit.docai.worker")


class DocumentWorker:
    """Orchestrates document preprocessing, OCR, layout segmentation, and classification with step-level idempotency."""

    def __init__(self, store: DocumentStore | None = None) -> None:
        self.store = store or DocumentStore()

    async def process_document(self, document_id: str) -> DocumentRecord:
        """Process document through the pipeline, resuming from the first non-completed step."""
        doc = await self.store.get_document(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # Idempotency check: if document is already completed, return immediately
        if doc.status == DocumentStatus.COMPLETED:
            logger.info("document_already_processed_idempotent", document_id=document_id)
            return doc

        await self.store.update_document(document_id, status=DocumentStatus.PROCESSING)

        content = self.store.get_document_content(doc.sha256, doc.filename)
        if not content:
            await self.store.update_document(
                document_id,
                status=DocumentStatus.FAILED,
                error="Binary document content missing from storage",
            )
            raise FileNotFoundError(f"Content for {document_id} not found on disk or MinIO")

        # Fetch existing completed steps to support resumability
        existing_steps = await self.store.get_document_steps(document_id)
        completed_step_names = {
            s.step_name for s in existing_steps if s.status == StepStatus.COMPLETED
        }

        try:
            # -----------------------------------------------------------------
            # Step 1: Preprocessing & Page Rendering
            # -----------------------------------------------------------------
            pages_data: list[tuple[np.ndarray, pymupdf.Page | None]] = []
            deskew_angles: list[float] = []

            t0 = time.perf_counter()
            if "PREPROCESS" in completed_step_names and doc.pages:
                logger.info(
                    "resuming_skipping_completed_step", step="PREPROCESS", document_id=document_id
                )
                # Re-render images for subsequent steps if needed
                if doc.mime_type == "application/pdf":
                    pages_data = render_pdf_pages_to_images(content)
                else:
                    img_arr, _ = render_image_bytes(content)
                    pages_data = [(img_arr, None)]
                deskew_angles = [p.deskew_angle for p in doc.pages]
            else:
                await self.store.record_step(document_id, "PREPROCESS", StepStatus.RUNNING)

                # Render pages
                if doc.mime_type == "application/pdf":
                    raw_pages = render_pdf_pages_to_images(content)
                else:
                    img_arr, _ = render_image_bytes(content)
                    raw_pages = [(img_arr, None)]

                # Deskew and denoise each page
                for img, pdf_page in raw_pages:
                    deskewed, angle = deskew_image(img)
                    denoised = denoise_image(deskewed, is_scanned=False)
                    pages_data.append((denoised, pdf_page))
                    deskew_angles.append(angle)

                dur_preprocess = (time.perf_counter() - t0) * 1000.0
                await self.store.record_step(
                    doc_id=document_id,
                    step_name="PREPROCESS",
                    status=StepStatus.COMPLETED,
                    duration_ms=round(dur_preprocess, 2),
                    details={"page_count": len(pages_data), "deskew_angles": deskew_angles},
                )
                completed_step_names.add("PREPROCESS")

            # -----------------------------------------------------------------
            # Step 2: OCR & Text Layer Extraction
            # -----------------------------------------------------------------
            page_texts: list[str] = []
            page_word_boxes: list[list[Any]] = []
            page_sources: list[str] = []

            t0 = time.perf_counter()
            if "OCR" in completed_step_names and doc.pages and all(p.text for p in doc.pages):
                logger.info("resuming_skipping_completed_step", step="OCR", document_id=document_id)
                page_texts = [p.text for p in doc.pages]
                page_word_boxes = [p.word_boxes for p in doc.pages]
                page_sources = [p.source for p in doc.pages]
            else:
                await self.store.record_step(document_id, "OCR", StepStatus.RUNNING)

                for page_img, pdf_page in pages_data:
                    text, word_boxes, source = extract_page_text_and_boxes(page_img, pdf_page)
                    page_texts.append(text)
                    page_word_boxes.append(word_boxes)
                    page_sources.append(source)

                dur_ocr = (time.perf_counter() - t0) * 1000.0
                await self.store.record_step(
                    doc_id=document_id,
                    step_name="OCR",
                    status=StepStatus.COMPLETED,
                    duration_ms=round(dur_ocr, 2),
                    details={
                        "sources": page_sources,
                        "total_words": sum(len(w) for w in page_word_boxes),
                    },
                )
                completed_step_names.add("OCR")

            # -----------------------------------------------------------------
            # Step 3: Layout Analysis & Table Segmentation
            # -----------------------------------------------------------------
            page_results: list[PageResult] = []

            t0 = time.perf_counter()
            if (
                "LAYOUT" in completed_step_names
                and doc.pages
                and all(p.layout_blocks for p in doc.pages)
            ):
                logger.info(
                    "resuming_skipping_completed_step", step="LAYOUT", document_id=document_id
                )
                page_results = doc.pages
            else:
                await self.store.record_step(document_id, "LAYOUT", StepStatus.RUNNING)

                for idx, (page_img, _) in enumerate(pages_data):
                    h, w = page_img.shape[:2]
                    w_boxes = page_word_boxes[idx]
                    layout_blks = segment_page_layout(page_img, w_boxes, page_idx=idx)

                    page_results.append(
                        PageResult(
                            page_idx=idx,
                            width=w,
                            height=h,
                            text=page_texts[idx],
                            source=page_sources[idx],
                            deskew_angle=deskew_angles[idx],
                            is_scanned=(page_sources[idx] != "native"),
                            word_boxes=w_boxes,
                            layout_blocks=layout_blks,
                        )
                    )

                dur_layout = (time.perf_counter() - t0) * 1000.0
                await self.store.record_step(
                    doc_id=document_id,
                    step_name="LAYOUT",
                    status=StepStatus.COMPLETED,
                    duration_ms=round(dur_layout, 2),
                    details={"total_blocks": sum(len(p.layout_blocks) for p in page_results)},
                )
                completed_step_names.add("LAYOUT")

            # -----------------------------------------------------------------
            # Step 4: Document Type Classification
            # -----------------------------------------------------------------
            t0 = time.perf_counter()
            all_text = " ".join(page_texts)
            doc_type = classify_document_type(all_text, doc.filename)

            dur_classify = (time.perf_counter() - t0) * 1000.0
            await self.store.record_step(
                doc_id=document_id,
                step_name="CLASSIFY",
                status=StepStatus.COMPLETED,
                duration_ms=round(dur_classify, 2),
                details={"predicted_type": doc_type.value},
            )

            # -----------------------------------------------------------------
            # Finalize Document Record
            # -----------------------------------------------------------------
            await self.store.update_document(
                document_id,
                status=DocumentStatus.COMPLETED,
                document_type=doc_type,
                page_count=len(page_results),
                pages=page_results,
            )

            final_doc = await self.store.get_document(document_id)
            return final_doc or doc

        except Exception as exc:
            logger.error(
                "document_processing_pipeline_failed", document_id=document_id, error=str(exc)
            )
            await self.store.update_document(
                document_id,
                status=DocumentStatus.FAILED,
                error=str(exc),
            )
            raise
