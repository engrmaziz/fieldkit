"""Synthetic delivery note generation and degradation engine for Halden Industrie (P4 M2).

Generates bilingual (German/English) delivery notes across 6 distinct visual templates:
- Templates 1-4: Modern Standard, Classic Industrial, Minimal Table, Split Header (Used for Train / Val / Seen Test)
- Templates 5-6: Dense Grid, Asymmetric Banner (Strictly Held-Out for Unseen Generalization Test)

Supports:
- Ground truth fields: supplier_name, supplier_address, delivery_note_no, po_number, delivery_date,
  line_items[{part_no, description, qty, unit}], total_qty.
- Augraphy-style 30% degradation: rotation (+-4 deg), Gaussian blur, JPEG artifacts, scanner noise, coffee stains.
- Donut ground_truth format: {"file_name": "...", "ground_truth": "{\"gt_parse\": {...}}"}
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Template definitions
TEMPLATES: dict[int, str] = {
    1: "modern_standard",
    2: "classic_industrial",
    3: "minimal_table",
    4: "split_header",
    5: "unseen_dense_grid",  # Held out
    6: "unseen_asymmetric",  # Held out
}

HELD_OUT_TEMPLATES: set[int] = {5, 6}

# German & English supplier pools
SUPPLIERS: list[dict[str, str]] = [
    {
        "name": "Knorr Hydraulik GmbH",
        "address": "Industriestrasse 14, 70565 Stuttgart, Deutschland",
        "lang": "de",
    },
    {
        "name": "Mannesmann Praezisionstechnik AG",
        "address": "Rheinuferstrasse 88, 40221 Duesseldorf, Deutschland",
        "lang": "de",
    },
    {
        "name": "Brose Antriebstechnik GmbH & Co. KG",
        "address": "Berliner Ring 1, 96052 Bamberg, Deutschland",
        "lang": "de",
    },
    {
        "name": "ZF Friedrichshafen Komponenten",
        "address": "Graf-von-Soden-Platz 1, 88046 Friedrichshafen, Deutschland",
        "lang": "de",
    },
    {
        "name": "Continental Dichtungssysteme Hannover",
        "address": "Vahrenwalder Str. 9, 30165 Hannover, Deutschland",
        "lang": "de",
    },
    {
        "name": "Apex Precision Components Ltd",
        "address": "Unit 4, Gateway Industrial Estate, Birmingham B24 9QR, UK",
        "lang": "en",
    },
    {
        "name": "Vortex Flow Technologies plc",
        "address": "12 Technology Parkway, Sheffield S9 2XH, UK",
        "lang": "en",
    },
    {
        "name": "EuroValve Industrial Supplies S.A.",
        "address": "Avenue Louise 240, 1050 Bruxelles, Belgique",
        "lang": "en",
    },
    {
        "name": "Nordic Seal & Bearing AB",
        "address": "Kanalvagen 14, 194 61 Upplands Vasby, Sweden",
        "lang": "en",
    },
    {
        "name": "Wroclaw Hydraulika Sp. z o.o.",
        "address": "ul. Grabiszynska 241, 53-234 Wroclaw, Polska",
        "lang": "de",
    },
]

HALDEN_RECIPIENT = {
    "de": "Halden Industrie GmbH\nWerk DE-HAM, Tor 3\nIndustriestieg 12, 21107 Hamburg",
    "en": "Halden Industrie GmbH\nPlant DE-HAM, Gate 3\nIndustriestieg 12, 21107 Hamburg, Germany",
}

PARTS: list[dict[str, str]] = [
    {"part_no": "PART-0104", "de": "Hydraulikventil 24V NG6", "en": "Hydraulic Valve 24V NG6", "unit": "STK"},
    {"part_no": "PART-0219", "de": "Radial-Wellendichtring 45x65x8", "en": "Radial Shaft Seal 45x65x8", "unit": "STK"},
    {"part_no": "PART-0342", "de": "Hochdruckschlauch 2SN DN16 1.5m", "en": "High Pressure Hose 2SN DN16 1.5m", "unit": "MTR"},
    {"part_no": "PART-0488", "de": "Zahnradpumpe 14ccm rechts", "en": "Gear Pump 14ccm Clockwise", "unit": "STK"},
    {"part_no": "PART-0511", "de": "O-Ring NBR 70 32x3.5mm", "en": "O-Ring NBR 70 32x3.5mm", "unit": "STK"},
    {"part_no": "PART-0673", "de": "Filterelement 10 Mikron", "en": "Filter Element 10 Micron", "unit": "STK"},
    {"part_no": "PART-0782", "de": "Druckbegrenzungsventil DBDS 10", "en": "Pressure Relief Valve DBDS 10", "unit": "STK"},
    {"part_no": "PART-0899", "de": "Hydraulikrohr E235N 22x2mm", "en": "Hydraulic Tube E235N 22x2mm", "unit": "MTR"},
    {"part_no": "PART-0915", "de": "Flanschverbindung SAE 3000 1 Zoll", "en": "Flange Coupling SAE 3000 1 Inch", "unit": "STK"},
    {"part_no": "PART-1024", "de": "Kugelhahn 2-Wege G1/2 Stahl", "en": "Ball Valve 2-Way G1/2 Steel", "unit": "STK"},
]


@dataclass
class DeliveryLineItem:
    part_no: str
    description: str
    qty: int
    unit: str


@dataclass
class DeliveryNoteGroundTruth:
    supplier_name: str
    supplier_address: str
    delivery_note_no: str
    po_number: str
    delivery_date: str
    line_items: list[DeliveryLineItem]
    total_qty: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "supplier_name": self.supplier_name,
            "supplier_address": self.supplier_address,
            "delivery_note_no": self.delivery_note_no,
            "po_number": self.po_number,
            "delivery_date": self.delivery_date,
            "line_items": [asdict(item) for item in self.line_items],
            "total_qty": self.total_qty,
        }


@dataclass
class DeliveryNoteRecord:
    record_id: str
    template_id: int
    template_name: str
    lang: str
    is_degraded: bool
    ground_truth: DeliveryNoteGroundTruth

    def to_donut_dict(self, file_name: str) -> dict[str, Any]:
        gt_data = {"gt_parse": self.ground_truth.to_dict()}
        return {
            "file_name": file_name,
            "ground_truth": json.dumps(gt_data, ensure_ascii=False),
        }


def generate_delivery_note_record(seed: int, template_id: int, lang: str = "de") -> DeliveryNoteRecord:
    """Generate ground truth fields for a single delivery note."""
    rng = random.Random(seed)

    # Filter suppliers by preferred language or sample
    matching_suppliers = [s for s in SUPPLIERS if s["lang"] == lang]
    if not matching_suppliers:
        matching_suppliers = SUPPLIERS
    supplier = rng.choice(matching_suppliers)

    # IDs
    year = rng.randint(2025, 2026)
    serial_dn = rng.randint(10000, 99999)
    serial_po = rng.randint(1000, 9999)
    prefix_dn = "LS" if lang == "de" else "DN"
    delivery_note_no = f"{prefix_dn}-{year}-{serial_dn}"
    po_number = f"PO-{year}-{serial_po}"

    # Date (YYYY-MM-DD)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    delivery_date = f"{year}-{month:02d}-{day:02d}"

    # Sample 1 to 5 line items
    item_count = rng.randint(1, 5)
    sampled_parts = rng.sample(PARTS, item_count)
    line_items: list[DeliveryLineItem] = []
    total_qty = 0

    for part in sampled_parts:
        qty = rng.choice([5, 10, 15, 20, 25, 50, 100])
        total_qty += qty
        desc = part[lang]
        unit = "STK" if lang == "de" and part["unit"] == "STK" else ("PCS" if lang == "en" and part["unit"] == "STK" else part["unit"])
        line_items.append(
            DeliveryLineItem(
                part_no=part["part_no"],
                description=desc,
                qty=qty,
                unit=unit,
            )
        )

    gt = DeliveryNoteGroundTruth(
        supplier_name=supplier["name"],
        supplier_address=supplier["address"],
        delivery_note_no=delivery_note_no,
        po_number=po_number,
        delivery_date=delivery_date,
        line_items=line_items,
        total_qty=total_qty,
    )

    return DeliveryNoteRecord(
        record_id=f"dn_{seed:06d}",
        template_id=template_id,
        template_name=TEMPLATES.get(template_id, f"template_{template_id}"),
        lang=lang,
        is_degraded=False,
        ground_truth=gt,
    )


# Visual Rendering Engine using PIL (1280x960 Page Images)
def render_delivery_note_image(record: DeliveryNoteRecord) -> np.ndarray:
    """Render a clean delivery note image according to its template style."""
    width, height = 960, 1280
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    gt = record.ground_truth
    lang = record.lang
    t_id = record.template_id

    # Common labels
    lbl_title = "LIEFERSCHEIN" if lang == "de" else "DELIVERY NOTE"
    lbl_dn = "Lieferschein-Nr.:" if lang == "de" else "Delivery Note No.:"
    lbl_po = "Bestellnummer:" if lang == "de" else "Purchase Order:"
    lbl_date = "Lieferdatum:" if lang == "de" else "Delivery Date:"
    lbl_recipient = "Empfaenger / Lieferanschrift:" if lang == "de" else "Deliver To / Shipping Address:"
    lbl_pos = "Pos." if lang == "de" else "Item"
    lbl_art = "Art.-Nr." if lang == "de" else "Part No."
    lbl_desc = "Bezeichnung / Artikel" if lang == "de" else "Description / Goods"
    lbl_qty = "Menge" if lang == "de" else "Quantity"
    lbl_unit = "Einh." if lang == "de" else "Unit"
    lbl_total = "Gesamtmenge:" if lang == "de" else "Total Quantity:"

    # Load system or default font
    font_title: Any
    font_head: Any
    font_body: Any
    font_bold: Any
    font_sm: Any
    try:
        font_title = ImageFont.truetype("arial.ttf", 26)
        font_head = ImageFont.truetype("arialbd.ttf", 15)
        font_body = ImageFont.truetype("arial.ttf", 13)
        font_bold = ImageFont.truetype("arialbd.ttf", 13)
        font_sm = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font_title = font_head = font_body = font_bold = font_sm = ImageFont.load_default()

    # Dispatch template renderers
    if t_id == 1:
        # Modern Standard: Clean two-column header with zebra striped table
        draw.text((50, 45), gt.supplier_name, fill=(20, 40, 90), font=font_title)
        draw.text((50, 85), gt.supplier_address, fill=(70, 70, 70), font=font_sm)

        # Meta box top right
        draw.rectangle([580, 45, 910, 165], outline=(180, 190, 210), width=2, fill=(245, 248, 253))
        draw.text((595, 55), lbl_title, fill=(20, 40, 90), font=font_head)
        draw.text((595, 85), f"{lbl_dn} {gt.delivery_note_no}", fill=(0, 0, 0), font=font_bold)
        draw.text((595, 110), f"{lbl_po} {gt.po_number}", fill=(0, 0, 0), font=font_body)
        draw.text((595, 135), f"{lbl_date} {gt.delivery_date}", fill=(0, 0, 0), font=font_body)

        # Recipient box
        draw.rectangle([50, 190, 450, 310], outline=(210, 210, 210), width=1)
        draw.text((65, 198), lbl_recipient, fill=(100, 100, 100), font=font_sm)
        draw.text((65, 225), HALDEN_RECIPIENT[lang], fill=(0, 0, 0), font=font_body)

        # Table Header
        y_table = 360
        draw.rectangle([50, y_table, 910, y_table + 32], fill=(230, 236, 248))
        draw.text((60, y_table + 8), lbl_pos, fill=(30, 30, 30), font=font_head)
        draw.text((120, y_table + 8), lbl_art, fill=(30, 30, 30), font=font_head)
        draw.text((280, y_table + 8), lbl_desc, fill=(30, 30, 30), font=font_head)
        draw.text((750, y_table + 8), lbl_qty, fill=(30, 30, 30), font=font_head)
        draw.text((850, y_table + 8), lbl_unit, fill=(30, 30, 30), font=font_head)

        curr_y = y_table + 34
        for idx, item in enumerate(gt.line_items, 1):
            fill_bg = (248, 250, 255) if idx % 2 == 0 else (255, 255, 255)
            draw.rectangle([50, curr_y, 910, curr_y + 36], fill=fill_bg)
            draw.line([50, curr_y + 36, 910, curr_y + 36], fill=(225, 225, 225), width=1)
            draw.text((65, curr_y + 10), str(idx), fill=(40, 40, 40), font=font_body)
            draw.text((120, curr_y + 10), item.part_no, fill=(0, 0, 0), font=font_bold)
            draw.text((280, curr_y + 10), item.description, fill=(0, 0, 0), font=font_body)
            draw.text((765, curr_y + 10), str(item.qty), fill=(0, 0, 0), font=font_bold)
            draw.text((855, curr_y + 10), item.unit, fill=(60, 60, 60), font=font_body)
            curr_y += 38

        # Total line
        draw.rectangle([50, curr_y + 10, 910, curr_y + 48], fill=(230, 236, 248))
        draw.text((580, curr_y + 20), lbl_total, fill=(20, 40, 90), font=font_head)
        draw.text((765, curr_y + 20), str(gt.total_qty), fill=(20, 40, 90), font=font_head)

    elif t_id == 2:
        # Classic Industrial: Bordered frame, DIN 5008 address window, boxed items
        draw.rectangle([30, 30, 930, 1250], outline=(0, 0, 0), width=2)
        draw.text((60, 50), gt.supplier_name.upper(), fill=(0, 0, 0), font=font_title)
        draw.text((60, 90), gt.supplier_address, fill=(60, 60, 60), font=font_sm)
        draw.line([30, 120, 930, 120], fill=(0, 0, 0), width=2)

        # Recipient left
        draw.rectangle([60, 140, 480, 280], outline=(150, 150, 150), width=1)
        draw.text((75, 150), f"Absender: {gt.supplier_name} | {gt.supplier_address}", fill=(120, 120, 120), font=font_sm)
        draw.text((75, 185), HALDEN_RECIPIENT[lang], fill=(0, 0, 0), font=font_body)

        # Metadata right
        draw.rectangle([510, 140, 900, 280], outline=(0, 0, 0), width=1)
        draw.text((525, 155), lbl_title, fill=(0, 0, 0), font=font_head)
        draw.text((525, 185), f"{lbl_dn} {gt.delivery_note_no}", fill=(0, 0, 0), font=font_bold)
        draw.text((525, 215), f"{lbl_po} {gt.po_number}", fill=(0, 0, 0), font=font_body)
        draw.text((525, 245), f"{lbl_date} {gt.delivery_date}", fill=(0, 0, 0), font=font_body)

        # Grid Table
        y_table = 330
        draw.rectangle([60, y_table, 900, y_table + 30], fill=(220, 220, 220), outline=(0, 0, 0), width=1)
        draw.text((70, y_table + 7), lbl_pos, fill=(0, 0, 0), font=font_bold)
        draw.text((130, y_table + 7), lbl_art, fill=(0, 0, 0), font=font_bold)
        draw.text((290, y_table + 7), lbl_desc, fill=(0, 0, 0), font=font_bold)
        draw.text((740, y_table + 7), lbl_qty, fill=(0, 0, 0), font=font_bold)
        draw.text((830, y_table + 7), lbl_unit, fill=(0, 0, 0), font=font_bold)

        curr_y = y_table + 30
        for idx, item in enumerate(gt.line_items, 1):
            draw.rectangle([60, curr_y, 900, curr_y + 35], outline=(0, 0, 0), width=1)
            draw.text((75, curr_y + 8), str(idx), fill=(0, 0, 0), font=font_body)
            draw.text((130, curr_y + 8), item.part_no, fill=(0, 0, 0), font=font_bold)
            draw.text((290, curr_y + 8), item.description, fill=(0, 0, 0), font=font_body)
            draw.text((750, curr_y + 8), str(item.qty), fill=(0, 0, 0), font=font_bold)
            draw.text((840, curr_y + 8), item.unit, fill=(0, 0, 0), font=font_body)
            curr_y += 35

        draw.rectangle([60, curr_y, 900, curr_y + 40], fill=(240, 240, 240), outline=(0, 0, 0), width=1)
        draw.text((550, curr_y + 10), lbl_total, fill=(0, 0, 0), font=font_bold)
        draw.text((750, curr_y + 10), f"{gt.total_qty} STK", fill=(0, 0, 0), font=font_bold)

    elif t_id == 3:
        # Minimal Table: Clean typography with subtle rule dividers
        draw.text((60, 60), lbl_title, fill=(50, 50, 50), font=font_title)
        draw.text((60, 110), f"{lbl_dn} {gt.delivery_note_no}", fill=(0, 0, 0), font=font_bold)
        draw.text((60, 135), f"{lbl_po} {gt.po_number}", fill=(80, 80, 80), font=font_body)
        draw.text((60, 160), f"{lbl_date} {gt.delivery_date}", fill=(80, 80, 80), font=font_body)

        draw.text((550, 60), gt.supplier_name, fill=(0, 0, 0), font=font_head)
        draw.text((550, 90), gt.supplier_address, fill=(100, 100, 100), font=font_sm)
        draw.text((550, 130), lbl_recipient, fill=(100, 100, 100), font=font_sm)
        draw.text((550, 155), HALDEN_RECIPIENT[lang], fill=(0, 0, 0), font=font_sm)

        draw.line([60, 250, 900, 250], fill=(60, 60, 60), width=2)
        y_table = 270
        draw.text((65, y_table), lbl_art, fill=(60, 60, 60), font=font_bold)
        draw.text((250, y_table), lbl_desc, fill=(60, 60, 60), font=font_bold)
        draw.text((760, y_table), lbl_qty, fill=(60, 60, 60), font=font_bold)
        draw.text((850, y_table), lbl_unit, fill=(60, 60, 60), font=font_bold)
        draw.line([60, y_table + 25, 900, y_table + 25], fill=(180, 180, 180), width=1)

        curr_y = y_table + 35
        for item in gt.line_items:
            draw.text((65, curr_y), item.part_no, fill=(0, 0, 0), font=font_bold)
            draw.text((250, curr_y), item.description, fill=(0, 0, 0), font=font_body)
            draw.text((770, curr_y), str(item.qty), fill=(0, 0, 0), font=font_bold)
            draw.text((850, curr_y), item.unit, fill=(60, 60, 60), font=font_body)
            draw.line([60, curr_y + 25, 900, curr_y + 25], fill=(230, 230, 230), width=1)
            curr_y += 35

        draw.line([60, curr_y + 10, 900, curr_y + 10], fill=(60, 60, 60), width=2)
        draw.text((580, curr_y + 20), lbl_total, fill=(0, 0, 0), font=font_bold)
        draw.text((770, curr_y + 20), str(gt.total_qty), fill=(0, 0, 0), font=font_bold)

    elif t_id == 4:
        # Split Header: Symmetrical two-column top, colored info bar
        draw.rectangle([50, 50, 460, 200], fill=(245, 245, 245))
        draw.text((65, 60), "LIEFERANT / VENDOR", fill=(100, 100, 100), font=font_sm)
        draw.text((65, 85), gt.supplier_name, fill=(0, 0, 0), font=font_bold)
        draw.text((65, 115), gt.supplier_address, fill=(60, 60, 60), font=font_sm)

        draw.rectangle([500, 50, 910, 200], fill=(245, 245, 245))
        draw.text((515, 60), lbl_recipient, fill=(100, 100, 100), font=font_sm)
        draw.text((515, 85), HALDEN_RECIPIENT[lang], fill=(0, 0, 0), font=font_sm)

        # Info bar
        draw.rectangle([50, 220, 910, 275], fill=(40, 80, 140))
        draw.text((65, 238), f"{lbl_title}: {gt.delivery_note_no}", fill=(255, 255, 255), font=font_bold)
        draw.text((450, 238), f"{lbl_po}: {gt.po_number}", fill=(255, 255, 255), font=font_bold)
        draw.text((720, 238), f"{lbl_date}: {gt.delivery_date}", fill=(255, 255, 255), font=font_bold)

        # Table
        y_table = 310
        draw.rectangle([50, y_table, 910, y_table + 30], fill=(220, 230, 245))
        draw.text((60, y_table + 7), lbl_pos, fill=(0, 0, 0), font=font_bold)
        draw.text((120, y_table + 7), lbl_art, fill=(0, 0, 0), font=font_bold)
        draw.text((300, y_table + 7), lbl_desc, fill=(0, 0, 0), font=font_bold)
        draw.text((750, y_table + 7), lbl_qty, fill=(0, 0, 0), font=font_bold)
        draw.text((840, y_table + 7), lbl_unit, fill=(0, 0, 0), font=font_bold)

        curr_y = y_table + 32
        for idx, item in enumerate(gt.line_items, 1):
            draw.line([50, curr_y + 30, 910, curr_y + 30], fill=(200, 200, 200), width=1)
            draw.text((65, curr_y + 5), str(idx), fill=(60, 60, 60), font=font_body)
            draw.text((120, curr_y + 5), item.part_no, fill=(0, 0, 0), font=font_bold)
            draw.text((300, curr_y + 5), item.description, fill=(0, 0, 0), font=font_body)
            draw.text((760, curr_y + 5), str(item.qty), fill=(0, 0, 0), font=font_bold)
            draw.text((845, curr_y + 5), item.unit, fill=(60, 60, 60), font=font_body)
            curr_y += 34

        draw.rectangle([50, curr_y + 15, 910, curr_y + 50], fill=(240, 240, 240))
        draw.text((580, curr_y + 22), lbl_total, fill=(0, 0, 0), font=font_bold)
        draw.text((760, curr_y + 22), str(gt.total_qty), fill=(0, 0, 0), font=font_bold)

    elif t_id == 5:
        # Template 5 (HELD OUT): Dense Grid with sub-boxes & batch tracking rows
        draw.rectangle([40, 40, 920, 1240], outline=(40, 40, 40), width=2)
        # Top banner
        draw.rectangle([40, 40, 920, 100], fill=(50, 50, 50))
        draw.text((60, 55), f"HALDEN SUPPLY NETWORK - {lbl_title}", fill=(255, 255, 255), font=font_head)

        # 4-quadrant box
        draw.rectangle([55, 120, 480, 250], outline=(150, 150, 150), width=1)
        draw.text((65, 128), "SUPPLIER / SENDER:", fill=(100, 100, 100), font=font_sm)
        draw.text((65, 150), gt.supplier_name, fill=(0, 0, 0), font=font_bold)
        draw.text((65, 180), gt.supplier_address, fill=(50, 50, 50), font=font_sm)

        draw.rectangle([495, 120, 905, 250], outline=(150, 150, 150), width=1)
        draw.text((505, 128), "DOC METRICS:", fill=(100, 100, 100), font=font_sm)
        draw.text((505, 150), f"{lbl_dn} {gt.delivery_note_no}", fill=(0, 0, 0), font=font_bold)
        draw.text((505, 180), f"{lbl_po} {gt.po_number}", fill=(0, 0, 0), font=font_bold)
        draw.text((505, 210), f"{lbl_date} {gt.delivery_date}", fill=(0, 0, 0), font=font_body)

        # Dense table
        y_table = 280
        draw.rectangle([55, y_table, 905, y_table + 28], fill=(200, 200, 200), outline=(0, 0, 0), width=1)
        draw.text((65, y_table + 6), lbl_pos, fill=(0, 0, 0), font=font_bold)
        draw.text((115, y_table + 6), lbl_art, fill=(0, 0, 0), font=font_bold)
        draw.text((270, y_table + 6), lbl_desc, fill=(0, 0, 0), font=font_bold)
        draw.text((750, y_table + 6), lbl_qty, fill=(0, 0, 0), font=font_bold)
        draw.text((830, y_table + 6), lbl_unit, fill=(0, 0, 0), font=font_bold)

        curr_y = y_table + 28
        for idx, item in enumerate(gt.line_items, 1):
            draw.rectangle([55, curr_y, 905, curr_y + 32], outline=(120, 120, 120), width=1)
            draw.text((70, curr_y + 7), str(idx), fill=(0, 0, 0), font=font_body)
            draw.text((115, curr_y + 7), item.part_no, fill=(0, 0, 0), font=font_bold)
            draw.text((270, curr_y + 7), item.description, fill=(0, 0, 0), font=font_body)
            draw.text((760, curr_y + 7), str(item.qty), fill=(0, 0, 0), font=font_bold)
            draw.text((840, curr_y + 7), item.unit, fill=(0, 0, 0), font=font_body)
            curr_y += 32

        draw.rectangle([55, curr_y, 905, curr_y + 36], fill=(225, 225, 225), outline=(0, 0, 0), width=1)
        draw.text((580, curr_y + 9), lbl_total, fill=(0, 0, 0), font=font_bold)
        draw.text((760, curr_y + 9), str(gt.total_qty), fill=(0, 0, 0), font=font_bold)

    else:
        # Template 6 (HELD OUT): Asymmetric Corporate Banner with barcode stub
        # Asymmetric left vertical bar
        draw.rectangle([0, 0, 35, 1280], fill=(200, 50, 40))
        draw.text((70, 50), gt.supplier_name, fill=(30, 30, 30), font=font_title)
        draw.text((70, 95), gt.supplier_address, fill=(90, 90, 90), font=font_body)

        draw.text((620, 50), lbl_title, fill=(200, 50, 40), font=font_title)
        draw.text((620, 95), f"{lbl_dn} {gt.delivery_note_no}", fill=(0, 0, 0), font=font_bold)
        draw.text((620, 125), f"{lbl_po} {gt.po_number}", fill=(0, 0, 0), font=font_bold)
        draw.text((620, 155), f"{lbl_date} {gt.delivery_date}", fill=(0, 0, 0), font=font_body)

        # Recipient
        draw.rectangle([70, 190, 480, 290], fill=(245, 245, 245))
        draw.text((85, 200), lbl_recipient, fill=(120, 120, 120), font=font_sm)
        draw.text((85, 225), HALDEN_RECIPIENT[lang], fill=(0, 0, 0), font=font_sm)

        # Barcode visual mock
        draw.rectangle([620, 200, 890, 260], fill=(255, 255, 255), outline=(0, 0, 0), width=1)
        for bx in range(630, 880, 5):
            if (bx // 5) % 2 == 0:
                draw.line([bx, 210, bx, 250], fill=(0, 0, 0), width=2)

        # Table
        y_table = 340
        draw.rectangle([70, y_table, 900, y_table + 32], fill=(240, 240, 240))
        draw.line([70, y_table + 32, 900, y_table + 32], fill=(200, 50, 40), width=2)
        draw.text((80, y_table + 7), lbl_pos, fill=(0, 0, 0), font=font_bold)
        draw.text((140, y_table + 7), lbl_art, fill=(0, 0, 0), font=font_bold)
        draw.text((310, y_table + 7), lbl_desc, fill=(0, 0, 0), font=font_bold)
        draw.text((750, y_table + 7), lbl_qty, fill=(0, 0, 0), font=font_bold)
        draw.text((840, y_table + 7), lbl_unit, fill=(0, 0, 0), font=font_bold)

        curr_y = y_table + 36
        for idx, item in enumerate(gt.line_items, 1):
            draw.text((85, curr_y + 6), str(idx), fill=(80, 80, 80), font=font_body)
            draw.text((140, curr_y + 6), item.part_no, fill=(0, 0, 0), font=font_bold)
            draw.text((310, curr_y + 6), item.description, fill=(0, 0, 0), font=font_body)
            draw.text((760, curr_y + 6), str(item.qty), fill=(0, 0, 0), font=font_bold)
            draw.text((845, curr_y + 6), item.unit, fill=(80, 80, 80), font=font_body)
            draw.line([70, curr_y + 30, 900, curr_y + 30], fill=(230, 230, 230), width=1)
            curr_y += 34

        draw.rectangle([70, curr_y + 10, 900, curr_y + 45], fill=(248, 248, 248))
        draw.text((580, curr_y + 18), lbl_total, fill=(200, 50, 40), font=font_bold)
        draw.text((760, curr_y + 18), str(gt.total_qty), fill=(0, 0, 0), font=font_bold)

    return np.array(img)


# Degradation Engine (Augraphy-style 30% Scanned Degradation)
def apply_degradation_pipeline(img: np.ndarray, seed: int | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply realistic scan artifacts: rotation (+-4 deg), blur, JPEG artifacts, coffee stain."""
    rng = random.Random(seed)
    effects: dict[str, Any] = {}
    h, w = img.shape[:2]
    out = img.copy()

    # 1. Subtle Affine Rotation (+-4 deg) with white padding
    angle = rng.uniform(-4.0, 4.0)
    effects["rotation_deg"] = round(angle, 2)
    center = (w / 2.0, h / 2.0)
    rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
    out = cv2.warpAffine(out, rot_mat, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))

    # 2. Gaussian Blur (Scanner lens defect)
    k_size = rng.choice([3, 5])
    out = cv2.GaussianBlur(out, (k_size, k_size), sigmaX=rng.uniform(0.6, 1.2))
    effects["blur_ksize"] = k_size

    # 3. Random Gaussian / Sensor Noise
    noise = np.random.normal(0, rng.uniform(3, 8), out.shape).astype(np.float32)
    out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # 4. Coffee Stain / Water Blotch Overlay (50% probability among degraded)
    if rng.random() < 0.5:
        stain_x = rng.randint(w // 4, 3 * w // 4)
        stain_y = rng.randint(h // 4, 3 * h // 4)
        radius_x = rng.randint(40, 90)
        radius_y = rng.randint(40, 80)
        overlay = out.copy()
        cv2.ellipse(
            overlay,
            (stain_x, stain_y),
            (radius_x, radius_y),
            angle=rng.randint(0, 180),
            startAngle=0,
            endAngle=360,
            color=(185, 205, 225),  # BGR for light brown/sepia tint
            thickness=-1,
        )
        alpha = rng.uniform(0.12, 0.25)
        out = cv2.addWeighted(overlay, alpha, out, 1 - alpha, 0)
        effects["coffee_stain"] = True
    else:
        effects["coffee_stain"] = False

    # 5. JPEG Compression Artifacts
    jpeg_quality = rng.randint(30, 60)
    effects["jpeg_quality"] = jpeg_quality
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
    _, encimg = cv2.imencode(".jpg", out, encode_param)
    decoded = cv2.imdecode(encimg, cv2.IMREAD_COLOR)
    if decoded is not None:
        out = decoded

    return out, effects


class DeliveryNoteGenerator:
    """Batch generator partitioning dataset into train, val, and strictly held-out test."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_dataset(
        self,
        count: int = 8000,
        split_ratio: dict[str, float] | None = None,
        output_dir: Path | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        if split_ratio is None:
            split_ratio = {"train": 0.7, "val": 0.15, "test": 0.15}

        seen_templates = [1, 2, 3, 4]
        unseen_templates = [5, 6]

        dataset: dict[str, list[dict[str, Any]]] = {
            "train": [],
            "val": [],
            "seen_test": [],
            "unseen_test": [],
        }

        # Calculate partition sizes
        # E.g., for 8000: ~5600 train, ~1200 val, ~600 seen_test, ~600 unseen_test
        n_unseen = int(count * split_ratio["test"] * 0.5)
        n_seen_test = int(count * split_ratio["test"] * 0.5)
        n_val = int(count * split_ratio["val"])
        n_train = count - (n_unseen + n_seen_test + n_val)

        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            for split in ["train", "val", "seen_test", "unseen_test"]:
                (output_dir / split / "images").mkdir(parents=True, exist_ok=True)

        current_seed = self.seed

        # Helper to generate slice
        def _gen_slice(split_name: str, n_items: int, template_pool: list[int]) -> None:
            nonlocal current_seed
            meta_entries: list[dict[str, Any]] = []

            for _ in range(n_items):
                t_id = self.rng.choice(template_pool)
                lang = "de" if self.rng.random() < 0.65 else "en"
                rec = generate_delivery_note_record(seed=current_seed, template_id=t_id, lang=lang)
                clean_img = render_delivery_note_image(rec)

                # 30% degraded
                is_deg = self.rng.random() < 0.30
                rec.is_degraded = is_deg
                if is_deg:
                    final_img, _ = apply_degradation_pipeline(clean_img, seed=current_seed)
                else:
                    final_img = clean_img

                file_name = f"{rec.record_id}.png"
                if output_dir:
                    img_path = output_dir / split_name / "images" / file_name
                    cv2.imwrite(str(img_path), final_img)

                donut_entry = rec.to_donut_dict(file_name)
                dataset_item = {
                    "record_id": rec.record_id,
                    "template_id": rec.template_id,
                    "template_name": rec.template_name,
                    "lang": rec.lang,
                    "is_degraded": is_deg,
                    "file_name": file_name,
                    "donut_meta": donut_entry,
                    "ground_truth": rec.ground_truth.to_dict(),
                }
                dataset[split_name].append(dataset_item)
                meta_entries.append(donut_entry)
                current_seed += 1

            if output_dir:
                meta_file = output_dir / split_name / "metadata.jsonl"
                with meta_file.open("w", encoding="utf-8") as f:
                    for entry in meta_entries:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Generate each split ensuring strict template isolation
        _gen_slice("train", n_train, seen_templates)
        _gen_slice("val", n_val, seen_templates)
        _gen_slice("seen_test", n_seen_test, seen_templates)
        _gen_slice("unseen_test", n_unseen, unseen_templates)

        return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic delivery notes for Donut fine-tuning.")
    parser.add_argument("--count", type=int, default=8000, help="Total number of notes to generate.")
    parser.add_argument("--output-dir", type=str, default="data/docai/delivery_notes", help="Output directory.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args()

    out_path = Path(args.output_dir)
    generator = DeliveryNoteGenerator(seed=args.seed)
    print(f"Generating {args.count} synthetic delivery notes into {out_path}...")
    dataset = generator.generate_dataset(count=args.count, output_dir=out_path)

    print("Generation complete:")
    for split, items in dataset.items():
        templates = sorted({x["template_id"] for x in items})
        degraded_pct = round(sum(1 for x in items if x["is_degraded"]) / max(1, len(items)) * 100, 1)
        print(f"  {split:12s}: {len(items):5d} items | Templates: {templates} | Degraded: {degraded_pct}%")


if __name__ == "__main__":
    main()
