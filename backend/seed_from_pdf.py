"""Extract the owner-supplied inventory table into a repeatable JSON seed.

Usage: python seed_from_pdf.py /path/to/inventory.pdf /path/to/products.json
This is an offline import utility; the server seeds from the generated JSON.
"""
import json
import re
import sys
from pathlib import Path

import pymupdf


RULES = [
    ("Safety & PPE", r"GOGGLE|GLOVE|WELDING SCREEN"),
    ("Sanitary & Bathroom", r"WASH BAS|WASH BES|TOWEL|SEAT COVER|URINAL|EWC|JET SPRAY|DRAIN|SHOWER|HEALTH FAUCET"),
    ("Adhesives & Sealants", r"FEVICOL|FEVI |FOAM|SILICON|SEAL|SOLVENT|SOLN|GROUT|M.SEAL|BOND TITE|BONDTITE|GRIPPO"),
    ("Paints & Coatings", r"PAINT|PRIMER|PUTTY|EMULSON|OPUS|THINNER|COLOUR|GREY|WHITE|RED OXIDE|SEALER|JAPAN|DAMPROOF|APEX|SPARKLE"),
    ("Door & Window Hardware", r"HINGE|LOCK|ALDROP|TOWER BOLT|DOOR|HANDLE|MAGNET|CLOSER"),
    ("Power Tools", r"MACHINE|GRINDER|DRILL|CUTTER|SAW |VIBRAT|BLOWER|BREAKER"),
    ("Hand Tools", r"HAMMER|PLIER|WRENCH|SPANNER|FILE|TROWEL|LEVEL|SCREW DRIVER|MEASURING| TEP"),
    ("Fasteners & Hardware", r"SCREW|BOLT|NUT|NAIL|ANCHOR|WASHER|WASER|RIVET|STUD|FASTNER"),
    ("Plumbing Supplies", r"PVC|CPVC|UPVC|PIPE|ELBO| LBO|TEE|COUPLER|VALVE|BEND|REDUCER|NIPPLE|TRAP|FAUCET|COCK|SHINK|FLUSH|TANK"),
    ("Construction Materials", r"WELDING|WIRE|PLATE|MESH|CENTRING|CHAIN|CEMENT|POP "),
    ("Electrical", r"INSULATION|TESTER|CABLE|MOTOR|PUMP"),
]


def category(name):
    upper = name.upper()
    for label, keywords in RULES:
        if re.search(keywords, upper):
            return label
    return "General & Misc"


def extract(pdf_path):
    result = []
    document = pymupdf.open(pdf_path)
    for page in document:
        lines = {}
        for word in page.get_text("words"):
            x, y, _, _, text, *_ = word
            key = round(y, 1)
            lines.setdefault(key, []).append((x, text))
        for words in lines.values():
            name = " ".join(text for x, text in sorted(words) if 69 < x < 280).strip()
            price_text = " ".join(text for x, text in sorted(words) if 450 < x < 520).strip()
            sku = " ".join(text for x, text in sorted(words) if x < 65).strip()
            if not name or not re.fullmatch(r"\d+(?:\.\d+)?", price_text):
                continue
            if name.upper() in {"NAME", "PRODUCT DETAILS"}:
                continue
            result.append({"name": name, "salePrice": float(price_text), "category": category(name),
                           "originalCode": sku or None})
    return result


if __name__ == "__main__":
    records = extract(sys.argv[1])
    path = Path(sys.argv[2])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Extracted {len(records)} inventory rows to {path}")
    print("Unique names:", len({row["name"] for row in records}))