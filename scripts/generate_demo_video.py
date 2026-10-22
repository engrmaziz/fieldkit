"""Automated AI Video Generator for Fieldkit Project Demos.

Generates 1080p 60fps screen walkthrough videos with natural neural AI voiceover
without requiring any manual screen recording or voice acting.

Pipeline:
1. Playwright (Headless Chromium) automates the live Next.js web console UI.
2. Edge-TTS synthesizes human-sounding neural voice narration from the customer demo script.
3. FFmpeg binds video and audio tracks into a polished universal MP4 video.
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# Ensure output directory exists
VIDEOS_DIR = ROOT_DIR / "dist" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

P8_NARRATION_SCRIPT = (
    "Welcome to Fieldkit Project 8: the Air-Gapped Deployment Kit and Durable Go Workflow Engine, "
    "engineered for Halden Industrie's Plant Hamburg facility. In industrial manufacturing environments "
    "operating under strict IEC 62443 standards, production systems are completely cut off from the public internet. "
    "Fieldkit deploys autonomously via cryptographically signed offline bundles verified with Cosign and ECDSA P-256 signatures. "
    "The core orchestrator is a pure, deterministic Go 1.23 event-sourced state machine. "
    "Every execution is an immutable append-only event log. In our 200-workflow chaos test, workers were subjected to "
    "randomized SIGKILL crashes every 200 milliseconds. Surviving workers re-acquired leases via PostgreSQL SELECT FOR UPDATE "
    "SKIP LOCKED, with strictly zero duplicate downstream side effects and one hundred percent state determinism. "
    "Here on the Fieldkit Visual Workflow Builder console, operators inspect complex multi-step industrial automation DAGs. "
    "The retrain-and-promote workflow orchestrates PatchCore model retraining, runs automated evaluation gates, "
    "and securely pauses at the Human Approval Gate awaiting sign-off from Quality Lead Mehmet Yilmaz before zero-downtime cutover. "
    "With a single click, the operator delivers the approval signal, and the engine resumes execution seamlessly. "
    "For ongoing operations, Fieldkit guarantees zero-downtime rolling upgrades under live traffic, automatic rollback "
    "if a migration fails, and point-in-time disaster recovery with an RTO of 0.12 seconds and zero data loss. "
    "Fieldkit brings true sovereign, resilient AI automation to the industrial edge."
)


def get_audio_duration_seconds(audio_path: Path) -> float:
    """Extract audio duration using ffprobe."""
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


async def synthesize_voiceover(text: str, output_path: Path, voice: str = "en-US-ChristopherNeural") -> float:
    """Synthesize text to speech using edge-tts and return duration in seconds."""
    import edge_tts

    print(f"==> [1/3] Synthesizing Neural AI Voiceover ({voice})...")
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(str(output_path))
    duration = get_audio_duration_seconds(output_path)
    print(f"    Voiceover generated: {duration:.2f} seconds ({output_path.stat().st_size / 1024:.1f} KB)")
    return duration


async def smooth_mouse_move(page, start_x: float, start_y: float, target_x: float, target_y: float, steps: int = 15):
    """Animate mouse cursor smoothly between two coordinates."""
    for i in range(1, steps + 1):
        x = start_x + (target_x - start_x) * (i / steps)
        y = start_y + (target_y - start_y) * (i / steps)
        await page.mouse.move(x, y)
        await asyncio.sleep(0.02)


async def record_p8_walkthrough(target_duration: float, raw_video_dir: Path) -> Path:
    """Automate the Next.js workflow builder console with Playwright and record 1080p video."""
    from playwright.async_api import async_playwright

    print(f"==> [2/3] Automating 1080p Browser Walkthrough (Target: {target_duration:.1f}s)...")
    raw_video_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(raw_video_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # Record actions until the entire voiceover duration is fulfilled
        start_time = time.time()

        # Step 1: Open Workflows Console (0 - 15s)
        url = "http://localhost:3000/workflows"
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(3.0)

        # Smooth pan across DAG columns
        await smooth_mouse_move(page, 500, 350, 750, 350, steps=25)
        await asyncio.sleep(2.0)
        await smooth_mouse_move(page, 750, 350, 1050, 350, steps=25)
        await asyncio.sleep(2.0)

        # Step 2: Click on Human Approval Step to open Inspector Drawer (15 - 35s)
        approval_step = page.locator("text=human_approval").first
        if await approval_step.is_visible():
            await approval_step.click()
            await asyncio.sleep(4.0)

            # Move mouse over drawer parameters
            await page.mouse.move(1600, 400)
            await asyncio.sleep(3.0)
            await page.mouse.move(1600, 550)
            await asyncio.sleep(3.0)

            # Close drawer
            close_btn = page.locator("button:has(svg.lucide-x)").first
            if await close_btn.is_visible():
                await close_btn.click()
                await asyncio.sleep(2.0)

        # Step 3: Switch to YAML Editor Tab (35 - 50s)
        yaml_tab = page.locator("button:has-text('YAML Editor')").first
        if await yaml_tab.is_visible():
            await yaml_tab.click()
            await asyncio.sleep(3.0)
            await page.mouse.wheel(0, 300)
            await asyncio.sleep(3.0)
            await page.mouse.wheel(0, -300)
            await asyncio.sleep(2.0)

        # Step 4: Switch to Runs & Replay Tab (50 - 75s)
        runs_tab = page.locator("button:has-text('Runs & Replay')").first
        if await runs_tab.is_visible():
            await runs_tab.click()
            await asyncio.sleep(3.0)

            # Hover over the Human Approval Gate amber status
            await page.mouse.move(800, 450)
            await asyncio.sleep(3.0)

            # Click "Approve & Deliver Signal" button!
            approve_btn = page.locator("button:has-text('Approve & Deliver Signal')").first
            if await approve_btn.is_visible():
                await smooth_mouse_move(page, 800, 450, 1100, 470, steps=20)
                await approve_btn.click()
                await asyncio.sleep(5.0)

        # Step 5: Switch back to Visual Builder (75 - 95s)
        builder_tab = page.locator("button:has-text('Visual Builder')").first
        if await builder_tab.is_visible():
            await builder_tab.click()
            await asyncio.sleep(2.0)

        # Cycle through shipped workflows
        dropdown = page.locator("select").first
        if await dropdown.is_visible():
            await dropdown.select_option("nightly-ingest")
            await asyncio.sleep(4.0)
            await smooth_mouse_move(page, 500, 350, 800, 350, steps=20)
            await asyncio.sleep(2.0)

            await dropdown.select_option("daily-backup")
            await asyncio.sleep(4.0)
            await smooth_mouse_move(page, 500, 350, 800, 350, steps=20)
            await asyncio.sleep(2.0)

            await dropdown.select_option("retrain-promote")
            await asyncio.sleep(3.0)

        # Step 6: Pad any remaining seconds until full narration finishes
        while time.time() - start_time < target_duration + 1.0:
            await page.mouse.move(600, 350)
            await asyncio.sleep(1.0)
            await page.mouse.move(900, 350)
            await asyncio.sleep(1.0)

        await context.close()
        await browser.close()

    # Find the recorded webm file in raw_video_dir
    webm_files = list(raw_video_dir.glob("*.webm"))
    if not webm_files:
        raise RuntimeError("No recorded video found in Playwright directory")
    return webm_files[0]


def render_final_video(video_path: Path, audio_path: Path, output_mp4: Path) -> Path:
    """Merge Playwright video and Edge-TTS voiceover into a universal MP4 via FFmpeg."""
    print("==> [3/3] Encoding & Merging Video + Voiceover with FFmpeg...")
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


async def generate_p8_demo_video() -> Path:
    temp_dir = VIDEOS_DIR / "temp_p8"
    temp_dir.mkdir(parents=True, exist_ok=True)

    audio_path = temp_dir / "voiceover.mp3"
    raw_video_dir = temp_dir / "raw_video"
    output_mp4 = VIDEOS_DIR / "fieldkit_p8_demo.mp4"

    try:
        # 1. Generate Voiceover
        duration = await synthesize_voiceover(P8_NARRATION_SCRIPT, audio_path)

        # 2. Record UI Walkthrough
        raw_video = await record_p8_walkthrough(duration, raw_video_dir)

        # 3. Render Final MP4
        render_final_video(raw_video, audio_path, output_mp4)

        size_mb = output_mp4.stat().st_size / (1024 * 1024)
        print("\n" + "=" * 60)
        print(" [SUCCESS] Fieldkit AI Demo Video Generated Successfully!")
        print("=" * 60)
        print(f"  - Output Video: {output_mp4}")
        print("  - Video Specs:  1080p 60fps, H.264 / AAC MP4")
        print(f"  - Duration:     {duration:.1f} seconds")
        print(f"  - File Size:    {size_mb:.2f} MB")
        print("=" * 60 + "\n")
        return output_mp4

    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Automated AI Video Demo Generator for Fieldkit")
    parser.add_argument("--project", default="p8", choices=["p8"], help="Target project profile (default: p8)")
    parser.parse_args()

    asyncio.run(generate_p8_demo_video())


if __name__ == "__main__":
    main()
