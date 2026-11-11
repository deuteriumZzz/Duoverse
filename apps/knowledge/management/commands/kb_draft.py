"""Draft the missing knowledge blocks with Claude (Message Batches: half price, no rush) — everything lands as `draft`.

    manage.py kb_draft --dry-run                    # what would be drafted, how many requests
    manage.py kb_draft --only QUESTION,HABIT        # submit, wait, save drafts
    manage.py kb_draft --batch-id msgbatch_...      # collect a batch submitted earlier (same --only/--limit)

Nothing reaches users until an editor reviews and publishes the block in /staff/.
"""

import json
import re
import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.astrology.domain.interpret import PLANET
from apps.knowledge.catalog import SPHERES, Group, groups
from apps.knowledge.models import KnowledgeBlock

SYSTEM = """Ты пишешь тексты для Duoverse — сервиса о совместимости пары (астрология, числа, таро как символический слой и психология отношений как научный).

Правила:
1. Пиши по-русски, живо и по-человечески, как умный друг, а не астролог-гуру. Короткие предложения, без канцелярита и клише («вселенная ведёт вас», «звёзды говорят»).
2. Никаких вердиктов («вам нельзя быть вместе»), предсказаний событий (измена, расставание, болезнь, беременность, деньги, смерть) и диагнозов. Говори о склонностях и о том, что помогает.
3. Астрология — символический язык для размышления: не выдавай её за науку. Психологические советы опирай на исследования (Готтман, теория привязанности, EFT), но не выдумывай цифры и ссылки.
4. Сфера «Секс и телесность» — бережно и без откровенных описаний.
5. Подстановки имён пиши ровно в фигурных скобках из списка в задании, других фигурных скобок не используй. Падежи: {{x}} — именительный (Аня), {{x_gen}} — родительный (у Ани), {{x_dat}} — дательный (Ане), {{x_acc}} — винительный (Аню), {{x_ins}} — творительный (с Аней), {{x_pre}} — предложный (об Ане).
6. Верни ровно те ключи, что перечислены, в том же порядке, каждый один раз.

Справка по точкам карты (роль · потребность · тень):
{planets}

Сферы пары:
{spheres}
"""

PARAGRAPH = {"type": "string"}
SCHEMAS: dict[str, dict] = {
    "text": {"key": {"type": "string"}, "text": PARAGRAPH},
    "question": {"key": {"type": "string"}, "question": PARAGRAPH, "depth": {"type": "integer"}},
    "habit": {"key": {"type": "string"}, "title": PARAGRAPH, "cadence": PARAGRAPH, "duration": PARAGRAPH, "why": PARAGRAPH},
    "exercise": {
        "key": {"type": "string"},
        "title": PARAGRAPH,
        "minutes": {"type": "integer"},
        "steps": {"type": "array", "items": PARAGRAPH},
        "source": PARAGRAPH,
    },
}
FORBIDDEN = re.compile(r"измен[аиуы]|развед|расстан[еу]тесь|беремен|смерт|диагноз|вам нельзя|обречен|гарантир", re.I)


def schema(kind: str) -> dict:
    item = {"type": "object", "properties": SCHEMAS[kind], "required": list(SCHEMAS[kind]), "additionalProperties": False}
    return {
        "type": "object",
        "properties": {"items": {"type": "array", "items": item}},
        "required": ["items"],
        "additionalProperties": False,
    }


def system_prompt() -> str:
    planets = "\n".join(f"- {p}: {r} · {n} · {s}" for p, (r, n, s) in PLANET.items())
    spheres = "\n".join(f"- {k}: {t}" for k, t in SPHERES.items())
    return SYSTEM.format(planets=planets, spheres=spheres)


def user_prompt(g: Group) -> str:
    holders = ", ".join("{" + h + "}" for h in g.placeholders) or "нет — не используй фигурные скобки"
    return f"{g.brief}\n\nПодстановки: {holders}.\nКлючи по порядку:\n" + "\n".join(g.keys)


def validate(g: Group, items: list[dict]) -> tuple[dict[str, dict], list[str]]:
    """Keep well-formed items for the requested keys; report the rest."""
    ok: dict[str, dict] = {}
    problems: list[str] = []
    allowed = set(g.placeholders)
    for item in items:
        key = item.get("key", "")
        body = " ".join(str(v) for k, v in item.items() if k != "key")
        if key not in g.keys:
            problems.append(f"{key}: not requested")
        elif FORBIDDEN.search(body):
            problems.append(f"{key}: forbidden wording")
        elif set(re.findall(r"\{(\w+)\}", body)) - allowed:
            problems.append(f"{key}: unknown placeholder")
        elif len(body) < 20:
            problems.append(f"{key}: too short")
        else:
            ok[key] = item
    flagged = {p.split(": ")[0] for p in problems}
    problems += [f"{k}: missing" for k in g.keys if k not in ok and k not in flagged]
    return ok, problems


def to_block(g: Group, item: dict) -> dict[str, Any]:
    if g.kind == "text":
        return {"text": item["text"].strip(), "data": {}}
    return {"text": "", "data": {k: v for k, v in item.items() if k != "key"}}


class Command(BaseCommand):
    help = "Draft missing knowledge blocks with Claude (batch, status=draft)."

    def add_arguments(self, parser):
        parser.add_argument("--only", default="", help="comma-separated key prefixes, e.g. QUESTION,PAIRTYPE")
        parser.add_argument("--limit", type=int, default=0, help="at most this many requests")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--batch-id", default="", help="collect results of a batch submitted earlier")
        parser.add_argument("--locale", default="ru")

    def handle(self, *args, only="", limit=0, dry_run=False, batch_id="", locale="ru", **opts):
        have = set(KnowledgeBlock.objects.filter(locale=locale).values_list("key", flat=True))
        prefixes = tuple(p.strip().upper() + ":" for p in only.split(",") if p.strip())
        todo = [g for g in groups() if (not prefixes or g.keys[0].startswith(prefixes)) and any(k not in have for k in g.keys)]
        if limit:
            todo = todo[:limit]
        keys = sum(len([k for k in g.keys if k not in have]) for g in todo)
        self.stdout.write(f"{len(todo)} requests · {keys} missing keys")
        if dry_run or not (todo or batch_id):
            return
        client = self.client()
        by_id = {f"g{i}": g for i, g in enumerate(todo)}
        if not batch_id:
            batch = client.messages.batches.create(requests=[self.request(cid, g) for cid, g in by_id.items()])
            batch_id = batch.id
            self.stdout.write(f"batch {batch_id} submitted — if this stops, resume with --batch-id {batch_id}")
        while (batch := client.messages.batches.retrieve(batch_id)).processing_status != "ended":
            self.stdout.write(f"  {batch.processing_status}: {batch.request_counts.processing} in progress")
            time.sleep(30)
        self.save(client, batch_id, by_id, locale)

    def client(self):
        if not settings.ANTHROPIC_API_KEY:
            raise CommandError("ANTHROPIC_API_KEY is not set — put it in .env")
        import anthropic

        return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def request(self, custom_id: str, g: Group):
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request

        return Request(
            custom_id=custom_id,
            params=MessageCreateParamsNonStreaming(
                model=settings.LLM_MODEL,
                max_tokens=16000,
                output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema(g.kind)}},
                system=[{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_prompt(g)}],
            ),
        )

    def save(self, client, batch_id: str, by_id: dict[str, Group], locale: str) -> None:
        saved, problems = 0, []
        for result in client.messages.batches.results(batch_id):
            g = by_id.get(result.custom_id)
            if g is None:
                continue  # collected with a different --only/--limit than it was submitted with
            if result.result.type != "succeeded":
                problems.append(f"{g.keys[0]}…: {result.result.type}")
                continue
            msg = result.result.message
            text = next((b.text for b in msg.content if b.type == "text"), "")
            if msg.stop_reason != "end_turn" or not text:
                problems.append(f"{g.keys[0]}…: stopped with {msg.stop_reason}")
                continue
            ok, bad = validate(g, json.loads(text).get("items", []))
            problems += bad
            for key, item in ok.items():
                _, created = KnowledgeBlock.objects.get_or_create(
                    key=key,
                    locale=locale,
                    defaults={"domain": g.domain, "evidence_level": g.evidence, "status": "draft", **to_block(g, item)},
                )
                saved += created
        self.stdout.write(self.style.SUCCESS(f"{saved} drafts saved — review and publish them in /staff/"))
        for p in problems:
            self.stdout.write(f"  skipped {p}")
