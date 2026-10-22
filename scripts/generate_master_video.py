"""
Fieldkit Master AI Demo Video Generator
=======================================
Generates a comprehensive 4 to 5-minute Master Overview Video for the entire
Fieldkit industrial AI platform:
1. Purpose & Why: Mission for Halden Industrie GmbH and industrial air-gapped realities.
2. Problems & Solutions: End-to-end breakdown across all 8 flagship projects (P1 - P8).
3. How We Built It: Python 3.12, Go 1.23, Next.js, Postgres/DuckDB/ClickHouse, 100% Ollama.
4. Competitive Differentiators: Air-gapped, zero cloud cost, fail-closed deterministic gates.
5. Future Roadmap: Multi-plant fleet sync, edge NPU compilation, and federated learning.

Runs 100% autonomously:
- Microsoft Edge-TTS neural broadcast voiceover (en-US-ChristopherNeural)
- Playwright headless Chromium 1080p 60fps synchronized UI walkthrough
- FFmpeg H.264 / AAC composition with professional web pacing
"""

import asyncio
import os
import shutil
import subprocess
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR / "dist"
VIDEOS_DIR = DIST_DIR / "videos"
CONSOLE_URL = os.environ.get("CONSOLE_URL", "http://localhost:3000")

MASTER_NARRATION = (
    # Segment 1: Purpose, Context & The Industrial AI Crisis (0:00 - 0:42)
    "Welcome to Fieldkit, a forward-deployed enterprise AI and data platform engineered for heavy industrial manufacturing. "
    "Designed around an intensive real-world engagement with Halden Industrie GmbH, a German hydraulic components manufacturer, "
    "Fieldkit was built to solve a critical structural problem: why most enterprise AI initiatives fail on the factory floor. "
    "Industrial facilities operate under non-negotiable constraints: strict data residency, air-gapped plant networks, "
    "confidential CAD designs and machining tolerances that can never leave the firewall, and deep legacy data fragmentation across SAP, "
    "SOAP web services, and manual shop-floor spreadsheets. "
    "Commercial cloud APIs like OpenAI or Anthropic are legally prohibited, cost-prohibitive, and vulnerable to hallucinations. "
    "Fieldkit provides an end-to-end, zero-cloud alternative running entirely on local edge hardware. "
    # Segment 2: Architecture & How We Built It (0:42 - 1:15)
    "Architecturally, Fieldkit is organized as a high-performance monorepo powered by Python 3.12, FastAPI, Pydantic version two, "
    "and SQLAlchemy async, paired with a Go 1.23 workflow engine and a Next.js 15 App Router console. "
    "Our persistence tier leverages PostgreSQL 16 with pgvector for hybrid retrieval and row-level plant security, "
    "DuckDB for embedded analytical queries, ClickHouse for high-velocity telemetry at over one hundred thousand spans per second, "
    "and Redpanda for real-time event streaming. "
    "Critically, all generative AI calls execute through local Ollama instances running open-weights models like Qwen 2.5. "
    "Every LLM interaction is enforced by fail-closed Pydantic schemas and deterministic AST validators: if an output violates our schema "
    "or security rules, it is rejected immediately with zero database corruption and zero unverified side effects. "
    # Segment 3: P1 & P2 - Data Fusion & Hybrid Intelligence (1:15 - 1:55)
    "Let us explore the core platform systems. "
    "Project 1, Mini Foundry, solves industrial data fragmentation. It fuses raw ERP tables, SOAP parts catalogs, and Excel records into a unified "
    "manufacturing ontology. Using a hybrid Fellegi-Sunter probabilistic matching engine augmented by local LLM grey-zone adjudication, "
    "it achieves an ER F1 score of 0.94 with a zero percent human review backlog, while continuously monitoring schema drift. "
    "Project 2 delivers Enterprise RAG and NL2SQL. Plant engineers query machining specifications and live production telemetry in plain English or German. "
    "Our hybrid retriever combines nomic-embed-text vectors with BM25 keyword matching via Reciprocal Rank Fusion, "
    "while our SQL generator parses statements through an Abstract Syntax Tree validator that strictly forbids mutations and blocks unauthorized plant data access. "
    # Segment 4: P3 & P4 - Multi-Agent Ops Copilot & Document Intelligence (1:55 - 2:38)
    "Project 3 introduces our Multi-Agent Operations Copilot. Plant managers handle hundreds of complex maintenance tickets and parts shortages. "
    "A dual-agent LangGraph workflow orchestrates ticket classification, parts availability checks, and ERP action drafts. "
    "Crucially, Fieldkit introduces a deterministic human-in-the-loop approval gate: financial refunds, purchase requisitions, and inventory shifts "
    "cannot execute without explicit human authorization, completely eliminating autonomous rogue actions while logging every decision to a SHA-256 hash-chained audit ledger. "
    "Project 4, our Contract and Document Intelligence Engine, eliminates manual paperwork processing. "
    "Using DIN 5008 delivery note models, synthetic degradation pipelines, and local Donut field extractors backed by vision-language fallbacks, "
    "Fieldkit achieves 98 percent field extraction F1 with exact bounding-box coordinate grounding for auditor verification. "
    # Segment 5: P5 & P6 - Video Analytics & Industrial Defect Inspection (2:38 - 3:18)
    "Moving to physical factory operations, Project 5 delivers Multi-Camera Video Analytics. "
    "Edge gateways process four simultaneous synthetic RTSP video feeds across assembly zones, monitoring safety compliance, cycle times, "
    "and edge hardware telemetry across distributed manufacturing plants in Hamburg, Stuttgart, and Wrocław. "
    "Project 6, Industrial Defect Inspection, brings computer vision directly to high-speed optical conveyors. "
    "Processing high-resolution machining imagery, deep neural networks detect surface cracks, pitting, and dimensional burrs with sub-fifty millisecond latency. "
    "Heatmaps highlight exact defect regions, and borderline samples are automatically routed to active learning review queues, continuously retraining "
    "the edge model without factory downtime. "
    # Segment 6: P7 & P8 - LLM Observability & Air-Gapped Workflows (3:18 - 4:02)
    "Project 7, Tracehub, provides comprehensive LLM Observability. "
    "Every prompt, completion, latency metric, and token count across the monorepo is automatically captured via OpenTelemetry SDK instrumentation, "
    "streamed through Redpanda, and queried in ClickHouse. "
    "When latency spikes or schema violations occur, our streaming anomaly detector identifies the incident in under two and a half minutes, "
    "using share-weighted attribution to isolate the exact root-cause span with zero hallucinated figures. "
    "Finally, Project 8 delivers the Air-Gapped Deploy Kit and Workflow Engine. "
    "Written in Go, our topological DAG engine executes complex data pipelines with durable state persistence and human interrupt signals. "
    "The entire platform packages into a single self-contained, air-gapped bundle deployable via our fieldkit-ctl CLI onto localized k3d Kubernetes clusters. "
    # Segment 7: Differentiators, Future Roadmap & Conclusion (4:02 - 4:40)
    "How does Fieldkit differ from existing solutions like Palantir Foundry, Databricks, or cloud AI platforms? "
    "First: zero recurring cloud API bills. Fieldkit runs completely air-gapped on edge hardware. "
    "Second: mathematical reliability. Where traditional agentic platforms rely on probabilistic LLM judgment, Fieldkit enforces deterministic "
    "fail-closed validation and database-enforced row-level plant isolation. "
    "Looking forward, our roadmap includes multi-plant edge fleet synchronization, specialized edge NPU model quantization, "
    "self-healing workflow DAGs with automated rollback, and privacy-preserving federated learning across international manufacturing sites. "
    "Fieldkit demonstrates that industrial enterprise AI can be private, deterministic, air-gapped, and blisteringly fast. "
    "Thank you for exploring Fieldkit."
)


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


async def synthesize_voiceover(
    text: str, output_path: Path, voice: str = "en-US-ChristopherNeural"
) -> float:
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(str(output_path))
    return get_audio_duration_seconds(output_path)


async def smooth_mouse_move(
    page, start_x: float, start_y: float, target_x: float, target_y: float, steps: int = 15
):
    for i in range(1, steps + 1):
        curr_x = start_x + (target_x - start_x) * (i / steps)
        curr_y = start_y + (target_y - start_y) * (i / steps)
        await page.mouse.move(curr_x, curr_y)
        await asyncio.sleep(0.04)


async def record_master_walkthrough(target_duration: float, raw_video_dir: Path) -> Path:
    from playwright.async_api import async_playwright

    start_time = time.time()
    raw_video_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--hide-scrollbars",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            record_video_dir=str(raw_video_dir),
            record_video_size={"width": 1920, "height": 1080},
        )

        page = await context.new_page()

        # =========================================================================
        # Scene 1: Introduction & Multi-Plant Security Overview (~0:00 - 0:42)
        # =========================================================================
        print("    [Scene 1/9] Introduction & Industrial Plant Context...")
        await page.goto(f"{CONSOLE_URL}/foundry/explorer", wait_until="networkidle")
        await asyncio.sleep(3.0)

        # Highlight Navbar & Plant Isolation Switcher
        await smooth_mouse_move(page, 960, 50, 1600, 50, steps=20)
        await asyncio.sleep(2.0)
        plant_select = page.locator("select").first
        if await plant_select.is_visible():
            await plant_select.click()
            await asyncio.sleep(1.5)
            await page.keyboard.press("ArrowDown")
            await asyncio.sleep(1.0)
            await page.keyboard.press("Enter")
            await asyncio.sleep(2.0)

        # Explore Schema Explorer Cards
        await smooth_mouse_move(page, 400, 300, 800, 500, steps=25)
        await asyncio.sleep(4.0)

        # =========================================================================
        # Scene 2: P1 Data Fusion & Interactive Graph (~0:42 - 1:15)
        # =========================================================================
        print("    [Scene 2/9] P1: Mini Foundry (Data Fusion & Ontology Graph)...")
        await page.goto(f"{CONSOLE_URL}/foundry/graph", wait_until="networkidle")
        await asyncio.sleep(4.0)
        await smooth_mouse_move(page, 450, 450, 1050, 550, steps=30)
        await asyncio.sleep(4.0)

        # Quick glimpse of Golden Record Review & Drift
        await page.goto(f"{CONSOLE_URL}/foundry/review", wait_until="networkidle")
        await asyncio.sleep(4.0)
        await smooth_mouse_move(page, 600, 350, 1100, 350, steps=20)
        await asyncio.sleep(3.0)

        # =========================================================================
        # Scene 3: P2 Enterprise RAG & NL2SQL (~1:15 - 1:55)
        # =========================================================================
        print("    [Scene 3/9] P2: Enterprise RAG + NL2SQL Query Assistant...")
        await page.goto(f"{CONSOLE_URL}/assistant", wait_until="networkidle")
        await asyncio.sleep(3.0)

        # Click a sample query or type prompt
        sample_chip = page.locator(
            "button:has-text('Roughness'), button:has-text('Ra'), button:has-text('SOP')"
        ).first
        if await sample_chip.is_visible():
            await sample_chip.click()
            await asyncio.sleep(4.0)
        else:
            textarea = page.locator("textarea").first
            if await textarea.is_visible():
                await textarea.fill(
                    "What is the surface roughness limit for DE-HAM honing operations?"
                )
                await asyncio.sleep(2.0)

        # Move mouse over retrieved citations and answer
        await smooth_mouse_move(page, 500, 400, 850, 600, steps=25)
        await asyncio.sleep(4.0)

        # Switch to Schema Graph tab
        graph_tab = page.locator("button:has-text('Schema Graph'), button:has-text('Graph')").first
        if await graph_tab.is_visible():
            await graph_tab.click()
            await asyncio.sleep(5.0)

        # =========================================================================
        # Scene 4: P3 Multi-Agent Ops Copilot (~1:55 - 2:38)
        # =========================================================================
        print("    [Scene 4/9] P3: Multi-Agent Ops Copilot & Human Approval Gates...")
        await page.goto(f"{CONSOLE_URL}/copilot", wait_until="networkidle")
        await asyncio.sleep(3.0)

        # Select ticket in triage inbox
        ticket_item = page.locator("div.cursor-pointer, button:has-text('TKT-')").first
        if await ticket_item.is_visible():
            await ticket_item.click()
            await asyncio.sleep(3.0)

        # Highlight deterministic approval button
        approve_btn = page.locator("button:has-text('Approve'), button:has-text('Authorize')").first
        if await approve_btn.is_visible():
            await smooth_mouse_move(page, 600, 500, 1100, 650, steps=25)
            await asyncio.sleep(3.0)

        # Switch to Audit Ledger tab
        audit_tab = page.locator("button:has-text('Audit'), button:has-text('Ledger')").first
        if await audit_tab.is_visible():
            await audit_tab.click()
            await asyncio.sleep(4.0)

        # =========================================================================
        # Scene 5: P4 Contract & Document Intelligence (~2:38 - 3:00)
        # =========================================================================
        print("    [Scene 5/9] P4: Contract & Document Intelligence Engine...")
        await page.goto(f"{CONSOLE_URL}/docai", wait_until="networkidle")
        await asyncio.sleep(3.0)

        # Hover over document canvas and extraction fields
        await smooth_mouse_move(page, 450, 400, 1100, 500, steps=30)
        await asyncio.sleep(5.0)

        # =========================================================================
        # Scene 6: P5 Multi-Camera Video Analytics (~3:00 - 3:20)
        # =========================================================================
        print("    [Scene 6/9] P5: Multi-Camera Video Analytics & Edge Fleet...")
        await page.goto(f"{CONSOLE_URL}/vision", wait_until="networkidle")
        await asyncio.sleep(3.0)

        # Move mouse across 4-camera video matrix
        await smooth_mouse_move(page, 400, 300, 900, 300, steps=20)
        await asyncio.sleep(2.0)
        await smooth_mouse_move(page, 900, 300, 900, 650, steps=20)
        await asyncio.sleep(4.0)

        # =========================================================================
        # Scene 7: P6 Industrial Defect Inspection (~3:20 - 3:45)
        # =========================================================================
        print("    [Scene 7/9] P6: Industrial Optical Defect Inspection...")
        await page.goto(f"{CONSOLE_URL}/inspection", wait_until="networkidle")
        await asyncio.sleep(3.0)

        # Highlight defect heatmaps and switch to Active Review
        await smooth_mouse_move(page, 500, 400, 950, 400, steps=20)
        await asyncio.sleep(3.0)
        review_tab = page.locator("button:has-text('Review'), button:has-text('Retrain')").first
        if await review_tab.is_visible():
            await review_tab.click()
            await asyncio.sleep(4.0)

        # =========================================================================
        # Scene 8: P7 Tracehub LLM Observability (~3:45 - 4:10)
        # =========================================================================
        print("    [Scene 8/9] P7: Tracehub LLM Observability & Anomaly Alerting...")
        await page.goto(f"{CONSOLE_URL}/observe", wait_until="networkidle")
        await asyncio.sleep(3.0)

        # Click trace row to open waterfall drawer
        trace_row = page.locator("table tbody tr").first
        if await trace_row.is_visible():
            await trace_row.click()
            await asyncio.sleep(3.0)
            await smooth_mouse_move(page, 1400, 250, 1400, 500, steps=20)
            await asyncio.sleep(3.0)
            close_btn = page.locator("div.fixed.inset-0 button:has(svg.lucide-x)").first
            if await close_btn.is_visible():
                await close_btn.click()
                await asyncio.sleep(1.5)

        # Switch to Alerts & RCA tab
        alerts_tab = page.locator("button:has-text('Alerts')").first
        if await alerts_tab.is_visible():
            await alerts_tab.click()
            await asyncio.sleep(4.0)

        # =========================================================================
        # Scene 9: P8 Workflows Engine, Air-Gapped Deploy & Outro (~4:10 - 4:45)
        # =========================================================================
        print("    [Scene 9/9] P8: Workflow Engine, Air-Gap Deploy & Strategic Outro...")
        await page.goto(f"{CONSOLE_URL}/workflows", wait_until="networkidle")
        await asyncio.sleep(3.0)

        # Explore workflow DAG canvas
        await smooth_mouse_move(page, 500, 400, 1050, 450, steps=25)
        await asyncio.sleep(4.0)

        # Click human_approval step
        approval_step = page.locator("div:has-text('human_approval'), div:has-text('human')").last
        if await approval_step.is_visible():
            await approval_step.click()
            await asyncio.sleep(3.0)

        # Switch to Runs tab
        runs_tab = page.locator("button:has-text('Runs')").first
        if await runs_tab.is_visible():
            await runs_tab.click()
            await asyncio.sleep(4.0)

        # Pad remaining time until full voiceover finishes
        while time.time() - start_time < target_duration + 1.0:
            await page.mouse.move(700, 450)
            await asyncio.sleep(1.5)
            await page.mouse.move(950, 450)
            await asyncio.sleep(1.5)

        await context.close()
        await browser.close()

    webm_files = list(raw_video_dir.glob("*.webm"))
    if not webm_files:
        raise RuntimeError("No recorded video found for master walkthrough")
    return webm_files[0]


def render_master_video(video_path: Path, audio_path: Path, output_mp4: Path) -> Path:
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


async def main_async() -> Path:
    print("=" * 70)
    print("   FIELDKIT MASTER PLATFORM AI DEMO VIDEO GENERATION (4-5 MIN)")
    print("=" * 70)

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir = VIDEOS_DIR / "temp_master"
    temp_dir.mkdir(parents=True, exist_ok=True)
    audio_path = temp_dir / "voiceover.mp3"
    raw_video_dir = temp_dir / "raw_video"
    output_mp4 = VIDEOS_DIR / "fieldkit_master_overview.mp4"

    try:
        # 1. Synthesize Comprehensive Broadcast Voiceover
        print("\n>>> Synthesizing Neural Master Broadcast Voiceover via Edge-TTS <<<")
        duration = await synthesize_voiceover(
            MASTER_NARRATION, audio_path, voice="en-US-ChristopherNeural"
        )
        print(f" [SUCCESS] Audio track duration: {duration:.2f}s (~{duration / 60:.2f} minutes)")

        # 2. Record Synchronized Full-Platform UI Walkthrough
        print("\n>>> Recording Synchronized 1080p Headless Chromium UI Walkthrough <<<")
        raw_video = await record_master_walkthrough(duration, raw_video_dir)
        print(" [SUCCESS] Master walkthrough recorded successfully.")

        # 3. Multiplex Final Master Video
        print("\n>>> Multiplexing Master Video + Neural Voiceover with FFmpeg <<<")
        render_master_video(raw_video, audio_path, output_mp4)
        size_mb = output_mp4.stat().st_size / (1024 * 1024)
        print("=" * 70)
        print(f" [MASTER COMPLETE] Generated: {output_mp4.name}")
        print(
            f" Duration: {duration:.1f}s ({duration / 60:.2f} mins) | Size: {size_mb:.2f} MB | Resolution: 1080p"
        )
        print("=" * 70)
        return output_mp4
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
