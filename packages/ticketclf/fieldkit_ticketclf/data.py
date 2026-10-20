"""Data acquisition, synthetic corpus generation, and stratified splitting for ticket classification."""

from __future__ import annotations

import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

ALLOWED_QUEUES: set[str] = {
    "technical_defect",
    "order_delivery",
    "returns_rma",
    "billing_inquiry",
    "general_inquiry",
    "other",
}

ALLOWED_PRIORITIES: set[str] = {
    "low",
    "medium",
    "high",
    "critical",
}

QUEUE_DESCRIPTIONS: dict[str, str] = {
    "technical_defect": "Hardware malfunction, hydraulic leak, valve crack, pressure drop, sensor failure, or abnormal vibration.",
    "order_delivery": "Shipping delay, tracking number inquiry, customs clearance, missing delivery note, or consignment status.",
    "returns_rma": "Return merchandise authorization, defective part return, warranty exchange, or wrong size delivered.",
    "billing_inquiry": "Invoice correction, disputed price, tax discrepancy, credit memo, or payment terms.",
    "general_inquiry": "Technical data sheet request, CAD drawing download, compliance certificates (ISO 4413), or catalog inquiry.",
    "other": "Out-of-scope inquiries, marketing communications, facility requests, or unclassifiable text.",
}

# Real Halden entities and domain vocabulary
HALDEN_PARTS = ["HX-100", "HX-200", "HX-300", "HX-400", "HX-500", "HX-600"]
HALDEN_PLANTS = ["DE-HAM", "DE-STR", "PL-WRO"]
HALDEN_COMPONENTS = [
    ("hydraulic directional valve", "Wegeventil"),
    ("piston cylinder seal", "Kolbendichtung"),
    ("high-pressure pump casing", "Hochdruckpumpengehaeuse"),
    ("proportional valve manifold", "Proportionalventilblock"),
    ("pressure relief cartridge", "Druckbegrenzungsventil"),
    ("flange connector", "Flanschverbindung"),
]


def normalize_ticket_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize raw ticket dictionary fields and labels."""
    subject = str(raw.get("subject", "")).strip()
    body = str(raw.get("body", "")).strip()
    language = str(raw.get("language", "en")).strip().lower()
    if language not in ("en", "de"):
        language = "en"

    queue = str(raw.get("queue", "other")).strip().lower()
    if queue not in ALLOWED_QUEUES:
        queue = "other"

    priority = str(raw.get("priority", "medium")).strip().lower()
    if priority not in ALLOWED_PRIORITIES:
        priority = "medium"

    text = f"{subject}\n\n{body}" if subject else body

    return {
        "ticket_id": str(raw.get("ticket_id", f"t-{random.randint(10000, 99999)}")),
        "subject": subject,
        "body": body,
        "text": text,
        "language": language,
        "queue": queue,
        "priority": priority,
        "order_id": str(raw.get("order_id", "")) or None,
        "part_number": str(raw.get("part_number", "")) or None,
        "plant": str(raw.get("plant", "")) or None,
    }


def generate_ticket_corpus(n_tickets: int = 2000, seed: int = 42) -> list[dict[str, Any]]:
    """Generate a realistic, balanced multilingual support ticket corpus for Halden Industrie."""
    rng = random.Random(seed)
    tickets: list[dict[str, Any]] = []

    templates_en = {
        "technical_defect": [
            ("Severe oil leakage on {comp} ({part})", "During assembly at {plant}, oil is spraying from the seal. Pressure dropped to 30 bar. Immediate assistance required.", "critical"),
            ("Vibration and noise in {comp}", "The hydraulic pump generates an abnormal rattling sound when operating above 200 bar. Unit is installed on assembly line 3.", "high"),
            ("Surface pitting observed on {part}", "Visual inspection revealed 0.4mm micro-cracks on cylinder casing. Requesting technical assessment.", "medium"),
            ("Minor pressure fluctuation on {comp}", "We noticed slight pressure instability during cold startup on {part}.", "low"),
        ],
        "order_delivery": [
            ("Urgent shipment inquiry for PO-{po}", "Order PO-{po} for 50x {part} was scheduled for delivery to {plant} yesterday. Production is blocked.", "critical"),
            ("Tracking status missing for shipment #{po}", "We have not received tracking confirmation for our bulk order of {comp}. Please provide carrier details.", "medium"),
            ("Delivery note mismatch on consignment", "Received shipment yesterday at {plant}, but packing slip specifies {part} while invoice lists another.", "medium"),
            ("Estimated dispatch date for {part}", "Can you confirm when the next batch of {part} will dispatch from the warehouse?", "low"),
        ],
        "returns_rma": [
            ("RMA Request: Damaged {comp} in transit", "Carton arrived crushed at {plant} warehouse. 4x {part} damaged and unmountable. Need immediate RMA number.", "high"),
            ("Warranty return request for defective {part}", "Part failed after 200 operating hours due to internal valve blowout. Requesting warranty replacement under contract.", "high"),
            ("Return authorization for wrong part size", "We ordered flange connector 32mm, but received 25mm variant on PO-{po}. Requesting return label.", "medium"),
            ("Surplus stock return inquiry", "Inquiring about restocking fee for returning 10 unused {part} units.", "low"),
        ],
        "billing_inquiry": [
            ("Invoice dispute on PO-{po}", "Invoice INV-{po} charged 1,450 EUR per unit for {part}, but our contract price agreement stipulates 1,180 EUR.", "high"),
            ("Duplicate invoice received for {plant}", "We received duplicate invoices for the same consignment of {comp}. Please issue credit memo.", "medium"),
            ("VAT exemption certificate update", "Please update our tax identification number on future invoices for Poland plant {plant}.", "low"),
            ("Payment receipt confirmation request", "Please confirm receipt of wire transfer for invoice reference #{po}.", "low"),
        ],
        "general_inquiry": [
            ("DIN EN ISO 4413 Certificate for {part}", "Our customer audit requires official compliance declaration and pressure test certificates for {comp}.", "medium"),
            ("CAD 3D Step file request for {part}", "Our engineering design team requires 3D STEP models for mounting {comp} onto chassis.", "low"),
            ("Operating fluid compatibility specs", "Which synthetic ester hydraulic fluids are approved for {part} seals?", "medium"),
            ("Catalog and pricing list 2026/2027", "Please send updated technical component catalog for hydraulic valve manifolds.", "low"),
        ],
        "other": [
            ("Vendor introduction email", "We offer advanced CNC milling services for hydraulic component manufacturers in Europe.", "low"),
            ("Facility cafeteria catering question", "Inquiry regarding schedule for company event next Thursday.", "low"),
            ("Internal password reset reminder", "Automated notification: Please update your intranet credentials before expiry.", "low"),
        ],
    }

    templates_de = {
        "technical_defect": [
            ("Kritischer Druckabfall an {comp_de} ({part})", "Bei der Inbetriebnahme im Werk {plant} bricht der Betriebsdruck ploetzlich von 250 auf 40 bar ein. Produktionsstillstand droht.", "critical"),
            ("Oelleckage an Zylinderdichtung {part}", "Starker Hydraulikoelaustritt an der Kolbendichtung bei Lastwechseln. Ventilblock muss dringend getauscht werden.", "high"),
            ("Rattergeraeusche und Vibrationen bei {comp_de}", "Auffaellige Kavitationsgeraeusche an Pumpe {part} bei Volllast. Bitte um Pruefung.", "high"),
            ("Leichte Erwaermung der Flanschverbindung {part}", "Temperaturfuehler zeigt 75 Grad nach 4 Betriebsstunden an {comp_de}.", "medium"),
        ],
        "order_delivery": [
            ("Lieferverzug zu Bestellung PO-{po} ({plant})", "Die bestellten 20 Stueck {part} sollten am Montag im Werk {plant} eintreffen. Montagelinie steht still.", "critical"),
            ("Sendungsverfolgung fuer Lieferung PO-{po}", "Bitte senden Sie uns die Speditionsdaten und Trackingnummer fuer {comp_de}.", "medium"),
            ("Fehlender Lieferschein bei Wareneingang", "Die Palette mit {part} wurde heute ohne Frachtbrief und Pruefzeugnis angeliefert.", "medium"),
            ("Avisierung geplante Zustellung {part}", "Wann ist mit dem Versand der naechsten Tranche fuer Werk {plant} zu rechnen?", "low"),
        ],
        "returns_rma": [
            ("RMA-Anforderung: Beschaedigte Ware PO-{po}", "Lieferung von {comp_de} weist Transportschaden auf. Gehaeuse von {part} deformiert. Bitte RMA-Schein ausstellen.", "high"),
            ("Gewaehrleistungsfall fuer Ventil {part}", "Bruch der Rueckstellfeder nach 150 Betriebsstunden. Bitte um kostenlosen Ersatz.", "high"),
            ("Falschlieferung: Ruecksendung fuer {part}", "Es wurden falsche Flanschmasse geliefert. Wir benoetigen Ruecksendeetikett fuer Werk {plant}.", "medium"),
            ("Rueckfrage zu Retourenabwicklung", "Bitte um Information ueber Bearbeitungsstatus der Ruecksendung #{po}.", "low"),
        ],
        "billing_inquiry": [
            ("Rechnungskorrektur erforderlich zu PO-{po}", "Rechnung weicht vom Rahmenvertrag ab: Berechnet wurden 850 Euro statt 720 Euro je {part}.", "high"),
            ("Doppelt ausgestellte Rechnung fuer {plant}", "Fuer dieselbe Teillieferung {comp_de} liegen zwei unterschiedliche Rechnungsnummern vor.", "medium"),
            ("Gutschrift fuer zurueckgesendete Dichtungen", "Bitte um Bestaetigung der Gutschriftanzeige fuer Retoure #{po}.", "medium"),
            ("Zahlungszielverlaengerung gemaess Rahmenvertrag", "Bitte Zahlungsziel fuer Werk {plant} auf 60 Tage netto anpassen.", "low"),
        ],
        "general_inquiry": [
            ("Anforderung Werkszeugnis 3.1 nach EN 10204", "Fuer Abnahmepruefung an {part} benoetigen wir das Materialzertifikat der Schmelze.", "medium"),
            ("CAD-Modelldaten fuer {comp_de} benoetigt", "Konstruktionsabteilung benoetigt STEP-Dateien fuer Einbaumasse von {part}.", "low"),
            ("Freigabe biologisch abbaubarer Hydraulikoele", "Besteht Dichtungsvertraeglichkeit fuer HEES-Fluids bei Komponente {part}?", "medium"),
            ("Produktschulung fuer Servicetechniker", "Anfrage bzgl. Terminoptionen fuer Praezisionswartung von {part}.", "low"),
        ],
        "other": [
            ("Lieferantenanfrage Zerspanungswerkzeuge", "Wir bieten Hochleistungswerkzeuge fuer die spanende Bearbeitung in Hamburg.", "low"),
            ("Fundbuero Kantine Werk {plant}", "In der Kantine wurde ein Werksausweis aufgefunden.", "low"),
            ("Information Betriebsrat Sommerfest", "Erinnerung an Rueckmeldefrist fuer Mitarbeiterveranstaltung.", "low"),
        ],
    }

    # Generate n_tickets with realistic distribution (45% DE, 55% EN)
    queues = list(ALLOWED_QUEUES)
    weights = [0.30, 0.25, 0.20, 0.12, 0.10, 0.03]  # defect, delivery, rma, billing, general, other

    for idx in range(n_tickets):
        is_german = rng.random() < 0.45
        lang = "de" if is_german else "en"
        queue = rng.choices(queues, weights=weights, k=1)[0]
        part = rng.choice(HALDEN_PARTS)
        plant = rng.choice(HALDEN_PLANTS)
        po = str(rng.randint(21000, 99000))
        comp_pair = rng.choice(HALDEN_COMPONENTS)

        if is_german:
            templates = templates_de[queue]
            chosen = rng.choice(templates)
            comp_name = comp_pair[1]
            subject = chosen[0].format(comp_de=comp_name, part=part, plant=plant, po=po)
            body = chosen[1].format(comp_de=comp_name, part=part, plant=plant, po=po)
            priority = chosen[2]
        else:
            templates = templates_en[queue]
            chosen = rng.choice(templates)
            comp_name = comp_pair[0]
            subject = chosen[0].format(comp=comp_name, part=part, plant=plant, po=po)
            body = chosen[1].format(comp=comp_name, part=part, plant=plant, po=po)
            priority = chosen[2]

        record = {
            "ticket_id": f"TIC-{20260000 + idx}",
            "subject": subject,
            "body": body,
            "language": lang,
            "queue": queue,
            "priority": priority,
            "order_id": f"PO-{po}",
            "part_number": part,
            "plant": plant,
        }
        tickets.append(normalize_ticket_record(record))

    return tickets


def stratified_split(
    records: list[dict[str, Any]],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Deterministically stratify records by (language, queue)."""
    rng = random.Random(seed)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for r in records:
        key = f"{r['language']}_{r['queue']}"
        buckets[key].append(r)

    train_set: list[dict[str, Any]] = []
    val_set: list[dict[str, Any]] = []
    test_set: list[dict[str, Any]] = []

    for key in sorted(buckets.keys()):
        group = buckets[key]
        rng.shuffle(group)
        n = len(group)
        n_train = int(round(n * train_ratio))
        n_val = int(round(n * val_ratio))
        # Ensure at least 1 in val and test if group is large enough
        if n >= 3:
            n_train = max(1, min(n - 2, n_train))
            n_val = max(1, min(n - n_train - 1, n_val))

        train_set.extend(group[:n_train])
        val_set.extend(group[n_train : n_train + n_val])
        test_set.extend(group[n_train + n_val :])

    rng.shuffle(train_set)
    rng.shuffle(val_set)
    rng.shuffle(test_set)

    return train_set, val_set, test_set


def prepare_and_split_dataset(
    n_tickets: int = 2000,
    output_dir: Path | None = None,
    eval_path: Path | None = None,
    seed: int = 42,
) -> dict[str, list[dict[str, Any]]]:
    """Generate tickets, stratify split 70/15/15 by (language, queue), and save Parquet datasets."""
    tickets = generate_ticket_corpus(n_tickets=n_tickets, seed=seed)
    train_records, val_records, test_records = stratified_split(
        tickets, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15, seed=seed
    )

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        t_train = pa.Table.from_pylist(train_records)
        t_val = pa.Table.from_pylist(val_records)
        t_test = pa.Table.from_pylist(test_records)
        pq.write_table(t_train, output_dir / "train.parquet", compression="snappy")
        pq.write_table(t_val, output_dir / "val.parquet", compression="snappy")
        pq.write_table(t_test, output_dir / "test.parquet", compression="snappy")

    if eval_path:
        eval_path = Path(eval_path)
        eval_path.parent.mkdir(parents=True, exist_ok=True)
        t_eval = pa.Table.from_pylist(test_records)
        pq.write_table(t_eval, eval_path, compression="snappy")

    return {
        "train": train_records,
        "val": val_records,
        "test": test_records,
    }


def load_parquet_records(path: Path | str) -> list[dict[str, Any]]:
    """Load records from a parquet file into python dictionaries."""
    table = pq.read_table(str(path))
    result: list[dict[str, Any]] = table.to_pylist()
    return result


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    data_dir = repo_root / "data" / "p3"
    eval_file = repo_root / "evals" / "p3" / "clf_test.parquet"

    print("[*] Generating 2,000 multilingual tickets with stratified 70/15/15 split...")
    res = prepare_and_split_dataset(
        n_tickets=2000,
        output_dir=data_dir,
        eval_path=eval_file,
        seed=42,
    )
    print("[+] Datasets successfully emitted:")
    print(f"    - Train: {len(res['train'])} rows -> {data_dir / 'train.parquet'}")
    print(f"    - Val:   {len(res['val'])} rows -> {data_dir / 'val.parquet'}")
    print(f"    - Test:  {len(res['test'])} rows -> {data_dir / 'test.parquet'}")
    print(f"    - Eval:  {len(res['test'])} rows -> {eval_file}")
