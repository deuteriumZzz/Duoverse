"""«Карта желаний»: each partner lists what they'd love to get — a thing, an experience, a place — and the other can
quietly reserve an idea. The owner of a wish never learns it was reserved, so a gift stays a surprise. «Мечты на двоих»
are shared: either adds them, both see them, and they can be marked as come true.

Stored encrypted on Pair.wishes: [{"id", "kind", "title", "note", "link", "by": side, "taken": side | "", "done": bool}].
"""

import secrets
from urllib.parse import urlsplit

KINDS = {"thing": "Вещь", "experience": "Впечатление", "place": "Место", "dream": "Мечта на двоих"}
MAX_ENTRIES, TITLE_MAX, NOTE_MAX, LINK_MAX = 120, 80, 200, 300


def other(side: str) -> str:
    return "b" if side == "a" else "a"


def clean(form: dict[str, str], side: str) -> dict | None:
    """A wish from the form, or None: a known kind, a title, and a link only if it is a plain http(s) address."""
    kind = form.get("kind", "thing")
    title = " ".join(form.get("title", "").split())[:TITLE_MAX]
    link = form.get("link", "").strip()[:LINK_MAX]
    if kind not in KINDS or not title:
        return None
    if link and (urlsplit(link).scheme not in ("http", "https") or not urlsplit(link).netloc):
        return None
    note = " ".join(form.get("note", "").split())[:NOTE_MAX]
    return {"id": secrets.token_hex(4), "kind": kind, "title": title, "note": note, "link": link, "by": side, "taken": "", "done": False}


def view(wishes: list[dict], side: str) -> dict[str, list[dict]]:
    """What `side` may see: own gift ideas without any sign of a reservation, the partner's with «taken» only if it
    was you, and the shared dreams."""
    mine = [{**w, "taken": ""} for w in wishes if w["kind"] != "dream" and w["by"] == side]
    theirs = [{**w, "taken": w["taken"] if w["taken"] == side else ""} for w in wishes if w["kind"] != "dream" and w["by"] != side]
    return {"mine": mine, "theirs": theirs, "dreams": [w for w in wishes if w["kind"] == "dream"]}


def apply(wishes: list[dict], side: str, action: str, wish_id: str, new: dict | None = None) -> list[dict]:
    """add / delete (your own idea, or any dream) / reserve (toggle, only someone else's idea) / done (toggle a dream)."""
    if action == "add":
        return [*wishes, new] if new and len(wishes) < MAX_ENTRIES else wishes
    out = []
    for w in wishes:
        if w["id"] != wish_id:
            out.append(w)
        elif action == "delete" and (w["by"] == side or w["kind"] == "dream"):
            continue
        elif action == "reserve" and w["kind"] != "dream" and w["by"] != side and w["taken"] in ("", side):
            out.append({**w, "taken": "" if w["taken"] else side})
        elif action == "done" and w["kind"] == "dream":
            out.append({**w, "done": not w["done"]})
        else:
            out.append(w)
    return out


def ideas_for(wishes: list[dict], side: str) -> tuple[int, int]:
    """(gift ideas of `side`, how many are still free) — for the birthday reminder the other partner gets."""
    own = [w for w in wishes if w["kind"] != "dream" and w["by"] == side]
    return len(own), sum(1 for w in own if not w["taken"])


# star spots for «Мечты на двоих» in a 320 × 110 sky; past twelve dreams the pattern repeats a little lower and to the side
SKY = ((34, 70), (70, 30), (110, 62), (150, 24), (186, 72), (224, 36), (262, 66), (292, 28), (52, 96), (132, 92), (206, 98), (280, 94))


def sky(dreams: list[dict]) -> dict:
    """The dreams constellation: a star per dream (lit once it came true) and a line through the lit ones, in order."""
    stars = []
    for i, d in enumerate(dreams):
        x, y = SKY[i % len(SKY)]
        stars.append({"id": d["id"], "x": x + 9 * (i // len(SKY)), "y": y + 4 * (i // len(SKY)), "done": d["done"], "title": d["title"]})
    return {"stars": stars, "line": " ".join(f"{s['x']},{s['y']}" for s in stars if s["done"])}


def leave(wishes: list[dict], side: str) -> list[dict]:
    """When `side` leaves the pair: what they added goes, and their reservations on the other's ideas are lifted."""
    return [{**w, "taken": "" if w["taken"] == side else w["taken"]} for w in wishes if w["by"] != side]


if __name__ == "__main__":
    book = clean({"kind": "thing", "title": " Книга   про Японию ", "link": "https://example.com/book"}, "a")
    trip = clean({"kind": "dream", "title": "Поехать в Японию"}, "b")
    assert book["title"] == "Книга про Японию" and clean({"title": "x", "link": "javascript:alert(1)"}, "a") is None
    assert clean({"kind": "car", "title": "x"}, "a") is None and clean({"title": "   "}, "a") is None
    w = apply(apply([], "a", "add", "", book), "b", "add", "", trip)
    w = apply(w, "b", "reserve", book["id"])
    assert view(w, "a")["mine"][0]["taken"] == "" and view(w, "b")["theirs"][0]["taken"] == "b"  # Anya never sees it
    assert apply(w, "a", "reserve", book["id"]) == w and apply(w, "b", "delete", book["id"]) == w  # not yours to touch
    assert ideas_for(w, "a") == (1, 0) and ideas_for(apply(w, "b", "reserve", book["id"]), "a") == (1, 1)
    assert apply(w, "a", "done", trip["id"])[1]["done"] and len(apply(w, "a", "delete", trip["id"])) == 1  # dreams are shared
    gone = leave(w, "b")
    assert [x["title"] for x in gone] == ["Книга про Японию"] and gone[0]["taken"] == ""  # Misha's dream and reservation go
    night = sky([{"id": str(i), "done": i != 2, "title": ""} for i in (1, 2, 3)])
    assert [s["done"] for s in night["stars"]] == [True, False, True] and night["line"] == "34,70 110,62"
    assert sky([{"id": str(i), "done": False, "title": ""} for i in range(13)])["stars"][12]["x"] == 43  # the 13th shifts aside
    print("ok")
