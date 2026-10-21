"""Locust load test script for Fieldkit InspectAI Edge Service.

Simulates 50 concurrent shop-floor camera stations and quality audit terminals
streaming component inspection images, checking decision dispositions, viewing
heatmaps, and performing operator review triage.
"""

from __future__ import annotations

import io
import random

from locust import HttpUser, between, task


class InspectionLoadUser(HttpUser):
    wait_time = between(0.05, 0.2)

    def on_start(self) -> None:
        self.products = ["metal_nut", "steel_sheet", "screw", "grid", "tile"]
        # Pre-generate a 256x256 test image payload in JPEG format
        try:
            import cv2
            import numpy as np

            img = np.ones((256, 256, 3), dtype=np.uint8) * 128
            _, buf = cv2.imencode(".jpg", img)
            self.sample_jpeg = buf.tobytes()
        except ImportError:
            self.sample_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 200

    @task(6)
    def inspect_part_stream(self) -> None:
        """Simulate high-throughput camera frame inspection at conveyor station."""
        product_id = random.choice(self.products)
        part_id = f"locust_part_{random.randint(100000, 999999)}"

        files = {"file": ("part.jpg", io.BytesIO(self.sample_jpeg), "image/jpeg")}
        data = {"part_id": part_id}

        res = self.client.post(
            f"/inspect/{product_id}",
            files=files,
            data=data,
            name="/inspect/[product_id]",
        )
        if res.status_code == 200:
            res_data = res.json()
            insp_id = res_data.get("inspection_id")
            # If rejected or reviewed, sometimes fetch the heatmap
            if insp_id and res_data.get("disposition") in ("review", "reject"):
                if random.random() < 0.4:
                    self.client.get(
                        f"/inspect/heatmap/{insp_id}",
                        name="/inspect/heatmap/[id]",
                    )

    @task(3)
    def list_recent_inspections(self) -> None:
        """Simulate quality manager dashboard polling recent inspection records."""
        product_id = random.choice(self.products)
        self.client.get(
            f"/inspect/records?product_id={product_id}&limit=20",
            name="/inspect/records?product_id=[id]",
        )

    @task(2)
    def query_review_queue(self) -> None:
        """Simulate Mehmet / operator auditing pending review items."""
        self.client.get(
            "/inspect/records?disposition=review&reviewed_only=false&limit=15",
            name="/inspect/records?disposition=review",
        )

    @task(1)
    def list_products(self) -> None:
        """Simulate edge station catalog lookup."""
        self.client.get("/inspect/products", name="/inspect/products")
