"""Synthetic hospital data, corruption engine and gold sets (S15). Everything here is SYNTHETIC.

- Seeded: the same seed and arguments give byte-identical files.
- Base patients come from Synthea (patients.csv: birth date, sex) when a Synthea export is given,
  otherwise from the built-in seeded generator. Names and phones are Indian-style and synthetic either way.
- The clean truth file is the label source for gold sets. A person spot-checks and signs off the gold sets.
- Timelines follow the GI handover pathway shape: tumour board, booking, attendance, with on-time, late,
  missed and silent patients. Gap values here are only for making data, never clinical values.
"""
from __future__ import annotations

import csv
import json
import random
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

FIRST_F = ["Sunita", "Ananya", "Kavita", "Meena", "Pooja", "Lakshmi", "Rekha", "Asha", "Geeta", "Neha", "Farida",
           "Shabana", "Priya", "Savita", "Usha", "Radha", "Jyoti", "Kamala", "Nirmala", "Sarita"]
FIRST_M = ["Rajesh", "Vikram", "Mohan", "Suresh", "Arjun", "Ravi", "Imran", "Sanjay", "Anil", "Prakash", "Ramesh",
           "Deepak", "Harish", "Manoj", "Salim", "Gopal", "Vinod", "Ashok", "Rahul", "Kiran"]
LAST = ["Kumar", "Patel", "Devi", "Sharma", "Iyer", "Lal", "Singh", "Gupta", "Reddy", "Nair", "Khan", "Das", "Yadav",
        "Joshi", "Mehta", "Rao", "Verma", "Pillai", "Shaikh", "Mishra"]
DEVANAGARI = {"Sunita": "सुनीता", "Kavita": "कविता", "Meena": "मीना", "Pooja": "पूजा", "Rekha": "रेखा", "Asha": "आशा",
              "Geeta": "गीता", "Rajesh": "राजेश", "Vikram": "विक्रम", "Mohan": "मोहन", "Suresh": "सुरेश", "Ravi": "रवि",
              "Sanjay": "संजय", "Anil": "अनिल", "Ramesh": "रमेश", "Kumar": "कुमार", "Devi": "देवी", "Sharma": "शर्मा",
              "Lal": "लाल", "Singh": "सिंह", "Gupta": "गुप्ता", "Yadav": "यादव", "Verma": "वर्मा", "Patel": "पटेल"}
DIAGNOSES = ["Ca colon", "Ca rectum", "Ca stomach", "Ca oesophagus", "Ca pancreas", "Hepatocellular ca"]  # must never be ingested
HEADERS = ["Sr No", "Patient Name", "Age", "Sex", "Mobile No", "UHID", "Date", "Department", "Visit Type", "Status",
           "Next Appt Date", "Diagnosis"]
VISIT = {"tb_decision_recorded": ("Tumour Board", ""), "appointment_booked": ("Chemo booking", "Booked"),
         "appointment_attended": ("Chemo Day Care", "Attended"), "appointment_missed": ("Chemo Day Care", "DNA"),
         "surgery_recorded": ("Surgery", "Done")}
DEPT = {"tb_decision_recorded": "Tumour Board", "appointment_booked": "Medical Oncology",
        "appointment_attended": "Medical Oncology", "appointment_missed": "Medical Oncology", "surgery_recorded": "GI Surgery"}
SCENARIOS = [("on_time", 0.45), ("late_no_booking", 0.2), ("booked_not_attended", 0.1), ("missed", 0.1),
             ("not_yet_due", 0.1), ("silent_after_booking", 0.05)]


@dataclass
class Patient:
    pid: str
    name: str
    sex: str
    birth_year: int
    phone: str
    uhid: str
    scenario: str
    diagnosis: str
    events: list[dict[str, Any]] = field(default_factory=list)


def _phone(rng: random.Random) -> str:
    return str(rng.choice("6789")) + "".join(str(rng.randint(0, 9)) for _ in range(9))


def base_patients(n: int, seed: int, synthea_csv: Path | None = None) -> list[tuple[str, int]]:
    """(sex, birth_year) per patient. Synthea when given, else seeded built-in generator."""
    rng = random.Random(seed)
    if synthea_csv and synthea_csv.exists():
        out = []
        with open(synthea_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                out.append(("F" if row["GENDER"] == "F" else "M", int(row["BIRTHDATE"][:4])))
                if len(out) >= n:
                    break
        if len(out) >= n:
            return out
    return [(rng.choice("FM"), rng.randint(1945, 1990)) for _ in range(n)]


DEMO_SCENARIOS = [("on_time", 0.86), ("late_no_booking", 0.04), ("booked_not_attended", 0.03), ("missed", 0.03),
                  ("not_yet_due", 0.03), ("silent_after_booking", 0.01)]


def _scenario(rng: random.Random, mix: list[tuple[str, float]] = SCENARIOS) -> str:
    x, acc = rng.random(), 0.0
    for name, p in mix:
        acc += p
        if x < acc:
            return name
    return mix[0][0]


def make_patients(n: int, seed: int, as_of: date, synthea_csv: Path | None = None,
                  mix: list[tuple[str, float]] = SCENARIOS) -> list[Patient]:
    rng = random.Random(seed)
    out = []
    for i, (sex, by) in enumerate(base_patients(n, seed, synthea_csv)):
        first = rng.choice(FIRST_F if sex == "F" else FIRST_M)
        p = Patient(pid=f"SYN-{i:06d}", name=f"{first} {rng.choice(LAST)}", sex=sex, birth_year=by,
                    phone=_phone(rng), uhid=f"PT-{10000 + i}", scenario=_scenario(rng, mix), diagnosis=rng.choice(DIAGNOSES))
        tb = as_of - timedelta(days=rng.randint(3, 60))
        if p.scenario == "not_yet_due":
            tb = as_of - timedelta(days=rng.randint(1, 5))
        p.events.append({"type": "tb_decision_recorded", "date": tb})
        if p.scenario in ("on_time", "booked_not_attended", "missed", "silent_after_booking"):
            booked = tb + timedelta(days=rng.randint(1, 6))
            if booked <= as_of:
                appt = booked + timedelta(days=rng.randint(3, 10))
                p.events.append({"type": "appointment_booked", "date": booked, "appointment_date": appt})
                if p.scenario == "on_time" and appt <= as_of:
                    p.events.append({"type": "appointment_attended", "date": appt})
                elif p.scenario == "missed" and appt <= as_of:
                    p.events.append({"type": "appointment_missed", "date": appt})
        out.append(p)
    return out


def _fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def clean_rows(patients: list[Patient]) -> list[dict[str, Any]]:
    """Truth rows in a deterministic order (by date, then patient)."""
    rows = []
    for p in patients:
        for e in p.events:
            visit, status = VISIT[e["type"]]
            rows.append({"truth_patient": p.pid, "truth_event_type": e["type"], "truth_date": e["date"].isoformat(),
                         "truth_appointment_date": e["appointment_date"].isoformat() if e.get("appointment_date") else None,
                         "Patient Name": p.name, "Age": str(e["date"].year - p.birth_year), "Sex": p.sex,
                         "Mobile No": p.phone, "UHID": p.uhid, "Date": _fmt(e["date"]), "Department": DEPT[e["type"]],
                         "Visit Type": visit, "Status": status,
                         "Next Appt Date": _fmt(e["appointment_date"]) if e.get("appointment_date") else "",
                         "Diagnosis": p.diagnosis, "corruptions": []})
    rows.sort(key=lambda r: (r["truth_date"], r["truth_patient"], r["truth_event_type"]))
    for i, r in enumerate(rows, start=1):
        r["Sr No"] = str(i)
    return rows


# ---------- corruption engine ----------

DEFAULT_RATES = {"typo": 0.04, "devanagari_name": 0.03, "devanagari_digits": 0.02, "swap_dm": 0.03,
                 "two_digit_year": 0.03, "phone_format": 0.08, "wrong_phone": 0.01, "duplicate_patient": 0.03,
                 "blank_merged": 0.02}


def _typo(rng: random.Random, s: str) -> str:
    if len(s) < 4:
        return s
    i = rng.randint(1, len(s) - 2)
    op = rng.choice(["swap", "drop", "double"])
    if op == "swap":
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    if op == "drop":
        return s[:i] + s[i + 1:]
    return s[:i] + s[i] + s[i:]


def corrupt(rows: list[dict[str, Any]], seed: int, rates: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """Returns new rows. Each row lists its corruptions so gold sets know what was done."""
    rng = random.Random(seed + 7919)
    rates = {**DEFAULT_RATES, **(rates or {})}
    dup_of: dict[str, dict[str, str]] = {}
    out = []
    prev_dept = None
    for r in rows:
        r = {**r, "corruptions": list(r["corruptions"])}
        pid = r["truth_patient"]
        if pid not in dup_of and rng.random() < rates["duplicate_patient"]:
            # A second registration of the same person: new UHID and a spelling variant, same phone.
            dup_of[pid] = {"uhid": f"PT-9{rng.randint(1000, 9999)}", "name": _typo(rng, r["Patient Name"])}
        if pid in dup_of and rng.random() < 0.5:
            r["UHID"], r["Patient Name"] = dup_of[pid]["uhid"], dup_of[pid]["name"]
            r["corruptions"].append("duplicate_registration")
        if rng.random() < rates["typo"]:
            r["Patient Name"] = _typo(rng, r["Patient Name"])
            r["corruptions"].append("typo")
        if rng.random() < rates["devanagari_name"]:
            parts = r["Patient Name"].split()
            if all(p in DEVANAGARI for p in parts):
                r["Patient Name"] = " ".join(DEVANAGARI[p] for p in parts)
                r["corruptions"].append("devanagari_name")
        d = date.fromisoformat(r["truth_date"])
        if rng.random() < rates["swap_dm"]:
            r["Date"] = d.strftime("%m/%d/%Y")
            r["corruptions"].append("swap_dm" if d.day != d.month else "swap_dm_noop")
        elif rng.random() < rates["two_digit_year"]:
            r["Date"] = d.strftime("%d/%m/%y")
            r["corruptions"].append("two_digit_year")
        if rng.random() < rates["devanagari_digits"]:
            r["Date"] = r["Date"].translate(str.maketrans("0123456789", "०१२३४५६७८९"))
            r["corruptions"].append("devanagari_digits")
        if rng.random() < rates["phone_format"]:
            ph = r["Mobile No"]
            r["Mobile No"] = rng.choice([f"+91 {ph[:5]} {ph[5:]}", f"0{ph}", f"{ph[:5]}-{ph[5:]}"])
            r["corruptions"].append("phone_format")
        if rng.random() < rates["wrong_phone"]:
            ph = list(r["Mobile No"])
            j = rng.randrange(len(ph) - 4, len(ph))
            if ph[j].isdigit():
                ph[j] = str((int(ph[j]) + 1) % 10)
            r["Mobile No"] = "".join(ph)
            r["corruptions"].append("wrong_phone")
        if prev_dept == r["Department"] and rng.random() < rates["blank_merged"]:
            r["Department"] = ""  # a merged cell read back as blank
            r["corruptions"].append("blank_merged")
        prev_dept = r["Department"] or prev_dept
        out.append(r)
    return out


# ---------- writers ----------

def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEADERS)
        for r in rows:
            w.writerow([r[h] for h in HEADERS])


def write_xlsx(rows: list[dict[str, Any]], path: Path, excel_serial_rate: float = 0.0, seed: int = 0) -> None:
    """write_only streams rows. Some dates become real Excel date cells (serials) when asked."""
    from openpyxl import Workbook

    rng = random.Random(seed + 104729)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Register")
    ws.append(HEADERS)
    for r in rows:
        vals: list[Any] = [r[h] for h in HEADERS]
        if excel_serial_rate and not r["corruptions"] and rng.random() < excel_serial_rate:
            vals[HEADERS.index("Date")] = date.fromisoformat(r["truth_date"])
            r["corruptions"].append("excel_date_cell")
        ws.append(vals)
    wb.save(path)
    # openpyxl stamps the current time into docProps; pin it so seeded output is byte-identical.
    _pin_xlsx_times(path)


def _pin_xlsx_times(path: Path) -> None:
    import re
    import zipfile

    tmp = path.with_suffix(".tmp.xlsx")
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "docProps/core.xml":
                data = re.sub(rb"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", b"2026-01-01T00:00:00Z", data)
            zi = zipfile.ZipInfo(info.filename, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(zi, data)
    tmp.replace(path)


def write_truth(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps({k: v for k, v in r.items() if k not in ("Diagnosis",)}, ensure_ascii=False,
                               sort_keys=True) + "\n")


def stream_big_csv(path: Path, n_rows: int, seed: int, as_of: date) -> int:
    """Benchmark-size file without holding all rows in memory: patients are generated in blocks."""
    written = 0
    block = 2000
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEADERS)
        b = 0
        while written < n_rows:
            pats = make_patients(block, seed + b, as_of)
            for p in pats:
                p.pid, p.uhid = f"SYN-{b:04d}-{p.pid[4:]}", f"PT-{b:04d}{p.uhid[3:]}"
            rows = corrupt(clean_rows(pats), seed + b)
            for r in rows:
                if written >= n_rows:
                    break
                r["Sr No"] = str(written + 1)
                w.writerow([r[h] for h in HEADERS])
                written += 1
            b += 1
    return written


# ---------- register photos (scanned gold set) ----------

def _font(size: int) -> Any:
    from PIL import ImageFont

    for p in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


PHOTO_COLS = ["Patient Name", "Mobile No", "UHID", "Date", "Visit Type", "Status"]


def render_photo(rows: list[dict[str, Any]], path: Path, seed: int, rotate: int = 0, stamp: bool = False) -> None:
    from PIL import Image, ImageDraw

    rng = random.Random(seed)
    col_w = [300, 220, 170, 170, 220, 140]
    width, line_h = sum(col_w) + 60, 52
    img = Image.new("RGB", (width, 120 + line_h * (len(rows) + 1)), (250, 247, 238))
    d = ImageDraw.Draw(img)
    f = _font(26)
    d.text((30, 30), "OPD REGISTER  (SYNTHETIC)", fill=(40, 40, 40), font=_font(30))
    y = 90
    x = 30
    for c, wdt in zip(PHOTO_COLS, col_w, strict=True):
        d.text((x, y), c, fill=(20, 20, 60), font=f)
        x += wdt
    for r in rows:
        y += line_h
        x = 30
        for c, wdt in zip(PHOTO_COLS, col_w, strict=True):
            d.text((x + rng.randint(-3, 3), y + rng.randint(-3, 3)), str(r[c]), fill=(30, 30, 90), font=f)
            x += wdt
        d.line((20, y + line_h - 8, width - 20, y + line_h - 8), fill=(200, 200, 200), width=1)
    if stamp:
        cx, cy = rng.randint(300, width - 300), rng.randint(150, img.height - 80)
        d.ellipse((cx - 90, cy - 50, cx + 90, cy + 50), outline=(180, 40, 40), width=5)
        d.text((cx - 60, cy - 18), "VERIFIED", fill=(180, 40, 40), font=_font(30))
    if rotate:
        img = img.rotate(rotate, expand=True, fillcolor=(250, 247, 238))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=False)


# ---------- dataset ----------

@dataclass
class Dataset:
    rows: list[dict[str, Any]]
    patients: list[Patient]
    files: dict[str, str]


def build(out_dir: Path, n_patients: int = 300, seed: int = 42, as_of: date = date(2026, 10, 10),
          synthea_csv: Path | None = None, photos: int = 3, mix: list[tuple[str, float]] = SCENARIOS) -> Dataset:
    pats = make_patients(n_patients, seed, as_of, synthea_csv, mix)
    rows = corrupt(clean_rows(pats), seed)
    # Two registers, same column shape: the tumour board register and the chemo day list.
    files = {"register_csv": str(out_dir / "tumour_board_register.csv"),
             "register_xlsx": str(out_dir / "chemo_day_list.xlsx"), "truth": str(out_dir / "truth.jsonl")}
    write_csv([r for r in rows if r["truth_event_type"] == "tb_decision_recorded"], Path(files["register_csv"]))
    write_xlsx([r for r in rows if r["truth_event_type"] != "tb_decision_recorded"], Path(files["register_xlsx"]),
               excel_serial_rate=0.03, seed=seed)
    write_truth(rows, Path(files["truth"]))
    photo_rows = [r for r in rows if not r["corruptions"]][: photos * 8]
    for i in range(photos):
        p = out_dir / f"register_photo_{i + 1}.png"
        render_photo(photo_rows[i * 8:(i + 1) * 8], p, seed + i, rotate=[0, 90, 180][i % 3], stamp=i == 1)
        files[f"photo_{i + 1}"] = str(p)
    with open(out_dir / "photos_truth.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for i in range(photos):
            for r in photo_rows[i * 8:(i + 1) * 8]:
                f.write(json.dumps({"photo": f"register_photo_{i + 1}.png", **{c: r[c] for c in PHOTO_COLS},
                                    "truth_patient": r["truth_patient"], "truth_event_type": r["truth_event_type"],
                                    "truth_date": r["truth_date"]}, ensure_ascii=False, sort_keys=True) + "\n")
    meta = {"synthetic": True, "seed": seed, "as_of": as_of.isoformat(), "patients": n_patients, "rows": len(rows),
            "base": "synthea" if synthea_csv and synthea_csv.exists() else "builtin",
            "scenarios": {s: sum(1 for p in pats if p.scenario == s) for s, _ in mix}}
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    return Dataset(rows, pats, files)


def patient_dict(p: Patient) -> dict[str, Any]:
    d = asdict(p)
    d["events"] = [{**e, "date": e["date"].isoformat(),
                    **({"appointment_date": e["appointment_date"].isoformat()} if e.get("appointment_date") else {})}
                   for e in p.events]
    return d
