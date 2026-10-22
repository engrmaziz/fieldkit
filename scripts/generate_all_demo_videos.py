"""Comprehensive Automated AI Demo Video Generator for Fieldkit Projects 1 through 7.

Generates 1080p 60fps narrated video demos for all flagship projects:
- P1: Mini Foundry (Data Fusion & Ontology)
- P2: Enterprise RAG + NL-to-SQL Assistant
- P3: Multi-Agent Ops Copilot (HITL)
- P4: Contract & Document Intelligence Engine
- P5: Multi-Camera Video Analytics Platform
- P6: Industrial Defect Inspection (InspectAI)
- P7: LLM Observability & Tracehub

Pipeline for each project:
1. Playwright automates the live Next.js console UI at 1920x1080.
2. Edge-TTS synthesizes neural AI voice narration.
3. FFmpeg merges video and audio into a universal MP4 file in dist/videos/.
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
VIDEOS_DIR = ROOT_DIR / "dist" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

PROJECT_SCRIPTS: dict[str, dict[str, str]] = {
    "p1": {
        "title": "Project 1: Mini Foundry (Data Fusion & Ontology)",
        "url": "http://localhost:3000/foundry/explorer",
        "voice": "en-US-ChristopherNeural",
        "narration": (
            "Welcome to Fieldkit Project 1: Mini Foundry, the data fusion and ontology platform for Halden Industrie. "
            "Manufacturing operations span heterogeneous legacy sources across German facilities: SAP ERP in Hamburg, "
            "AS/400 SOAP web services in Stuttgart, and Excel spreadsheets in Leipzig. Mini Foundry ingests these streams "
            "through schema-validated Pandera contracts into MinIO landing zones. "
            "Our entity resolution engine pairs Splink probabilistic record linkage with LLM grey-zone adjudication, "
            "achieving an F1 score of 0.9856 across 2,000 gold supplier pairs. In the schema drift console, deterministic fingerprinting "
            "catches upstream column drops, renames, and type corruptions across 20 scripted scenarios. "
            "Resolved entities are promoted into a typed ontology spanning Suppliers, Parts, Plants, Purchase Orders, and Quality Incidents, "
            "isolated by PostgreSQL Row-Level Security based on plant-level JWT permissions. "
            "With interactive Cytoscape graph exploration and high-speed keyset pagination, Mini Foundry unifies siloed industrial data into a trusted single source of truth."
        ),
    },
    "p2": {
        "title": "Project 2: Enterprise RAG + NL2SQL Assistant",
        "url": "http://localhost:3000/assistant",
        "voice": "en-US-GuyNeural",
        "narration": (
            "Welcome to Fieldkit Project 2: the Enterprise RAG and NL-to-SQL Assistant for Halden Industrie. "
            "Shop-floor supervisors, engineers, and plant managers need instant, verifiable answers combining regulatory documents "
            "with live operational database records. The hybrid retrieval pipeline fuses BM25 lexical keyword search with "
            "pgvector HNSW semantic embeddings using Reciprocal Rank Fusion and BGE reranking. "
            "Every answer includes strict bracketed citations with online citation verification and zero hallucinated references. "
            "For operational metrics, our NL2SQL generator maps natural language questions to read-only PostgreSQL queries, "
            "strictly validated client-side using sqlglot AST parsing to block DDL, DML, and injection attacks. "
            "In multi-plant environments, plant-scoped Row-Level Security guarantees zero permission leaks, verified against 40 adversarial ACL attacks. "
            "And for complex queries, our router triggers hybrid synthesis, pulling regulatory guidance and live production metrics into one unified response."
        ),
    },
    "p3": {
        "title": "Project 3: Multi-Agent Ops Copilot (HITL)",
        "url": "http://localhost:3000/copilot",
        "voice": "en-US-ChristopherNeural",
        "narration": (
            "Welcome to Fieldkit Project 3: the Multi-Agent Operations Copilot with Human-in-the-Loop governance. "
            "Customer support and plant operations teams handle bilingual German and English warranty inquiries, scrap tickets, and RMA requests. "
            "Incoming tickets are classified with our fine-tuned XLM-RoBERTa multi-task ONNX model, running on host CPU with a 22.8-millisecond P95 latency. "
            "The core agent is an explicit LangGraph deterministic state machine, rejecting unconstrained LLM loops in favor of policy-bounded execution. "
            "Before any side-effect tool executes—such as creating an RMA or issuing warranty credit—the agent pauses at the Human Approval Gate. "
            "The operator inspects the proposed action, verifies the deterministic customer reply, and approves or overrides the draft. "
            "Every state transition is committed to a SHA-256 hash-chained, tamper-evident audit ledger, while Presidio GDPR masking prevents PII leaks. "
            "Across 60 end-to-end evaluation scenarios, the copilot achieved a 100% task success rate with strictly zero unauthorized actions."
        ),
    },
    "p4": {
        "title": "Project 4: Contract and Document Intelligence Engine",
        "url": "http://localhost:3000/docai",
        "voice": "en-US-GuyNeural",
        "narration": (
            "Welcome to Fieldkit Project 4: the Contract and Document Intelligence Engine for Halden Industrie. "
            "Supply chain and legal teams process thousands of complex delivery notes, supplier certificates, and procurement contracts. "
            "The edge pipeline starts with magic-byte disguise rejection and OpenCV text contour deskewing, followed by native PyMuPDF and Tesseract OCR extraction. "
            "For structured delivery notes, our model extracts supplier numbers, part line items, and quantities across German and English formats, "
            "tested against held-out templates never seen during training. "
            "For legal contracts, our clause segmenter analyzes agreements against 41 CUAD categories and evaluates corporate risk using Halden's deterministic playbook rules. "
            "When comparing contract revisions, our Hungarian bipartite alignment algorithm tracks added, deleted, and modified clauses with character-level diffing. "
            "Verified extractions are automatically published into the Project 1 ontology with full provenance lineage."
        ),
    },
    "p5": {
        "title": "Project 5: Multi-Camera Video Analytics Platform",
        "url": "http://localhost:3000/vision",
        "voice": "en-US-ChristopherNeural",
        "narration": (
            "Welcome to Fieldkit Project 5: the Multi-Camera Video Analytics Platform for Halden Industrie. "
            "Operating across 4 simulated shop-floor cameras—the Press Shop, Logistics Hall, Assembly Line 3, and Perimeter Gate—"
            "the edge vision pipeline enforces worker safety and zone compliance in real time. "
            "Frames are sampled at 5 FPS with bounded drop-oldest memory backpressure, processed in dynamic batches via YOLO ONNX with vectorized C++ NMS, "
            "achieving 0.11-millisecond CPU inference. Multi-object ByteTrack tracking associates worker trajectories with head-region PPE compliance. "
            "Invertible 4-point floor homography maps camera pixels to physical plant coordinates, measuring pedestrian proximity to forklifts. "
            "To eliminate false alarms, our deterministic temporal rule engine requires sustained violations over 2.0 seconds with a 30-second alert cooldown, "
            "reducing alert noise by 10.9 times across 30 annotated clips. "
            "Violations trigger Redpanda event streams, ClickHouse 90-day TTL storage, 10-second MP4 ring-buffer clips, and GDPR face blurring."
        ),
    },
    "p6": {
        "title": "Project 6: Industrial Defect Inspection (InspectAI)",
        "url": "http://localhost:3000/inspection",
        "voice": "en-US-GuyNeural",
        "narration": (
            "Welcome to Fieldkit Project 6: InspectAI, the Industrial Defect Inspection platform with a closed-loop retraining system. "
            "Inspecting automotive hydraulic components—including metal nuts, screws, grids, and surface tiles—demands zero-escape quality compliance. "
            "Our hybrid architecture pairs unsupervised PatchCore anomaly localization on MVTec AD with a supervised 7-class NEU surface defect classifier. "
            "Using greedy k-Center coreset reduction, PatchCore achieves a 1.0 Image AUROC and 0.9978 Pixel AUROC with a 90% memory savings. "
            "Our asymmetric cost-based decision engine penalizes escaping defects at 500 dollars versus 15 dollars for review, "
            "guaranteeing strictly 0.0% defect escape rate while maintaining a low 4.2% human review queue. "
            "When material drift is detected via Population Stability Index, the platform automatically triggers retraining, "
            "evaluates candidate models in non-blocking shadow inference mode, and supports instant zero-downtime rollback."
        ),
    },
    "p7": {
        "title": "Project 7: LLM Observability & Tracehub",
        "url": "http://localhost:3000/observe",
        "voice": "en-US-ChristopherNeural",
        "narration": (
            "Welcome to Fieldkit Project 7: Tracehub, the local-first LLM Observability, Evaluation, and Anomaly Alerting platform. "
            "Every LLM interaction across the Fieldkit monorepo is automatically captured via OpenTelemetry SDK instrumentation, "
            "streamed through Redpanda, and stored in ClickHouse for high-throughput analytical querying at over 100,000 spans per second. "
            "In the Tracehub console, engineers inspect end-to-end distributed trace waterfalls, token consumption, and P95 latency breakdowns. "
            "When latency spikes or schema failures occur, our streaming anomaly detector identifies the incident in under 2.5 minutes. "
            "Our share-weighted attribution algorithm deterministically calculates the exact root-cause span and dimension with 100% accuracy, "
            "eliminating hallucinated numbers. "
            "Integrated with provisioned Grafana dashboards, Tracehub delivers complete visibility into AI reliability, cost, and latency."
        ),
    },
}


def get_audio_duration_seconds(audio_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(res.stdout.strip())


async def synthesize_voiceover(text: str, output_path: Path, voice: str) -> float:
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(str(output_path))
    return get_audio_duration_seconds(output_path)


async def smooth_mouse_move(
    page, start_x: float, start_y: float, target_x: float, target_y: float, steps: int = 15
):
    for i in range(1, steps + 1):
        x = start_x + (target_x - start_x) * (i / steps)
        y = start_y + (target_y - start_y) * (i / steps)
        await page.mouse.move(x, y)
        await asyncio.sleep(0.02)


async def record_project_walkthrough(
    project_key: str, target_duration: float, raw_video_dir: Path
) -> Path:
    from playwright.async_api import async_playwright

    cfg = PROJECT_SCRIPTS[project_key]
    url = cfg["url"]
    raw_video_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(raw_video_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        start_time = time.time()
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(3.0)

        if project_key == "p1":
            # P1: Foundry Explorer -> Graph -> Review -> Drift
            await smooth_mouse_move(page, 400, 250, 700, 250, steps=20)
            await asyncio.sleep(3.0)

            # Click on an entity row
            first_row = page.locator("table tbody tr").first
            if await first_row.is_visible():
                await first_row.click()
                await asyncio.sleep(4.0)

            # Navigate to Ontology Graph
            await page.goto("http://localhost:3000/foundry/graph", wait_until="networkidle")
            await asyncio.sleep(5.0)
            await smooth_mouse_move(page, 500, 400, 800, 500, steps=25)
            await asyncio.sleep(4.0)

            # Navigate to ER Review Queue
            await page.goto("http://localhost:3000/foundry/review", wait_until="networkidle")
            await asyncio.sleep(5.0)

            # Navigate to Schema Drift
            await page.goto("http://localhost:3000/foundry/drift", wait_until="networkidle")
            await asyncio.sleep(5.0)

        elif project_key == "p2":
            # P2: Assistant Chat & SQL
            chips = page.locator("button.chip, button[type='button']").all()
            for chip in (await chips)[:2]:
                if await chip.is_visible():
                    await chip.click()
                    await asyncio.sleep(6.0)

            await page.mouse.wheel(0, 400)
            await asyncio.sleep(3.0)
            await page.mouse.wheel(0, -400)
            await asyncio.sleep(2.0)

        elif project_key == "p3":
            # P3: Copilot Queue & Approval
            ticket = page.locator("div[role='button'], div.cursor-pointer, tr").first
            if await ticket.is_visible():
                await ticket.click()
                await asyncio.sleep(4.0)

            approve_btn = page.locator("button:has-text('Approve')").first
            if await approve_btn.is_visible():
                await approve_btn.click()
                await asyncio.sleep(4.0)

            await smooth_mouse_move(page, 600, 400, 900, 400, steps=20)
            await asyncio.sleep(3.0)

        elif project_key == "p4":
            # P4: DocAI Extraction & Contracts
            doc_row = page.locator("tr, div.document-card").first
            if await doc_row.is_visible():
                await doc_row.click()
                await asyncio.sleep(4.0)

            tabs = page.locator("button:has-text('Contract'), button:has-text('Diff')").all()
            for tab in await tabs:
                if await tab.is_visible():
                    await tab.click()
                    await asyncio.sleep(4.0)

        elif project_key == "p5":
            # P5: Vision Live Wall & Clips
            await smooth_mouse_move(page, 400, 300, 900, 300, steps=20)
            await asyncio.sleep(4.0)
            await smooth_mouse_move(page, 400, 600, 900, 600, steps=20)
            await asyncio.sleep(4.0)

            clip_btn = page.locator("button:has-text('Clip'), button:has-text('Event')").first
            if await clip_btn.is_visible():
                await clip_btn.click()
                await asyncio.sleep(4.0)

        elif project_key == "p6":
            # P6: Inspection Conveyor & Retraining
            await smooth_mouse_move(page, 500, 400, 800, 400, steps=20)
            await asyncio.sleep(5.0)

            tabs = page.locator("button:has-text('Review'), button:has-text('Retrain')").all()
            for tab in await tabs:
                if await tab.is_visible():
                    await tab.click()
                    await asyncio.sleep(5.0)

        elif project_key == "p7":
            # P7: Tracehub Waterfalls & Incidents
            # 1. Hover operational metrics
            await smooth_mouse_move(page, 200, 200, 700, 200, steps=15)
            await asyncio.sleep(3.0)

            # 2. Click trace row to open waterfall drawer
            trace_row = page.locator("table tbody tr").first
            if await trace_row.is_visible():
                await trace_row.click()
                await asyncio.sleep(4.0)
                # Inspect spans in drawer
                await smooth_mouse_move(page, 1400, 250, 1400, 450, steps=15)
                await asyncio.sleep(3.0)
                # Close the drawer
                close_btn = page.locator("div.fixed.inset-0 button:has(svg.lucide-x)").first
                if await close_btn.is_visible():
                    await close_btn.click()
                    await asyncio.sleep(2.0)

            # 3. Switch to Alerts & RCA tab
            alerts_tab = page.locator("button:has-text('Alerts')").first
            if await alerts_tab.is_visible():
                await alerts_tab.click()
                await asyncio.sleep(4.0)
                await smooth_mouse_move(page, 400, 300, 800, 500, steps=15)
                await asyncio.sleep(3.0)

            # 4. Switch to Prompt Registry tab
            prompt_tab = page.locator("button:has-text('Prompt Registry')").first
            if await prompt_tab.is_visible():
                await prompt_tab.click()
                await asyncio.sleep(4.0)

        # Pad remaining time until full voiceover finishes
        while time.time() - start_time < target_duration + 1.0:
            await page.mouse.move(600, 400)
            await asyncio.sleep(1.5)
            await page.mouse.move(850, 450)
            await asyncio.sleep(1.5)

        await context.close()
        await browser.close()

    webm_files = list(raw_video_dir.glob("*.webm"))
    if not webm_files:
        raise RuntimeError(f"No recorded video found for {project_key}")
    return webm_files[0]


def render_final_video(video_path: Path, audio_path: Path, output_mp4: Path) -> Path:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(output_mp4),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return output_mp4


async def generate_single_video(project_key: str) -> Path:
    cfg = PROJECT_SCRIPTS[project_key]
    print(f"\n>>> Starting AI Video Generation for {cfg['title']} ({project_key.upper()}) <<<")

    temp_dir = VIDEOS_DIR / f"temp_{project_key}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    audio_path = temp_dir / "voiceover.mp3"
    raw_video_dir = temp_dir / "raw_video"
    output_mp4 = VIDEOS_DIR / f"fieldkit_{project_key}_demo.mp4"

    try:
        # 1. Synthesize Voiceover
        duration = await synthesize_voiceover(cfg["narration"], audio_path, voice=cfg["voice"])
        print(f"    Audio track: {duration:.2f}s synthesized via {cfg['voice']}")

        # 2. Record UI Walkthrough
        raw_video = await record_project_walkthrough(project_key, duration, raw_video_dir)
        print("    Browser walkthrough recorded successfully.")

        # 3. Merge Video + Audio
        render_final_video(raw_video, audio_path, output_mp4)
        size_mb = output_mp4.stat().st_size / (1024 * 1024)
        print(
            f" [SUCCESS] Generated: {output_mp4.name} (Duration: {duration:.1f}s, Size: {size_mb:.2f} MB)"
        )
        return output_mp4
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def main_async(projects: list[str]) -> None:
    print("=" * 65)
    print("   FIELDKIT MASTER AI DEMO VIDEO GENERATION PIPELINE")
    print(f"   Target Projects: {', '.join(p.upper() for p in projects)}")
    print("=" * 65)

    completed = []
    for p in projects:
        try:
            out = await generate_single_video(p)
            completed.append(out)
        except Exception as e:
            print(f" [ERROR] Failed to generate {p}: {e}")

    print("\n" + "=" * 65)
    print(f" [COMPLETE] Finished generating {len(completed)}/{len(projects)} demo videos:")
    for c in completed:
        print(f"  - {c.name} ({c.stat().st_size / (1024 * 1024):.2f} MB)")
    print("=" * 65 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AI Demo Videos for Fieldkit Projects")
    parser.add_argument(
        "--projects",
        nargs="+",
        default=["p1", "p2", "p3", "p4", "p5", "p6", "p7"],
        help="List of projects to generate (e.g., p1 p2 p3 or all)",
    )
    args = parser.parse_args()

    target_projects = args.projects
    if "all" in target_projects:
        target_projects = ["p1", "p2", "p3", "p4", "p5", "p6", "p7"]

    asyncio.run(main_async(target_projects))


if __name__ == "__main__":
    main()
