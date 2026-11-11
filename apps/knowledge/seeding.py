import json
from pathlib import Path

SEED_DIR = Path(__file__).parent / "seed"


def load_seed(block_model, locale: str = "ru") -> int:
    """Upsert seed blocks. Seed-owned blocks (never reviewed by an editor) follow the seed; edited ones are kept."""
    n = 0
    blocks = [b for f in sorted(SEED_DIR.glob(f"{locale}*.json")) for b in json.loads(f.read_text(encoding="utf-8"))]
    for b in blocks:
        obj, created = block_model.objects.get_or_create(key=b["key"], locale=locale, defaults={**b, "key": b["key"]})
        if not created and not obj.reviewed_by:
            for field in ("domain", "text", "data", "evidence_level"):
                setattr(obj, field, b[field])
            obj.save()
        n += 1
    return n
