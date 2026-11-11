"""Load GeoNames populated places (cities500, CC BY 4.0) into GeoPlace, with Russian names from data/places_ru.tsv.gz.

manage.py places_load                       # downloads cities500.zip from download.geonames.org
manage.py places_load --source cities500.zip
manage.py places_load --if-empty            # container start: only when the table is still empty
"""

import csv
import gzip
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.compatibility.models import GeoPlace
from apps.compatibility.places import search_key

URL = "https://download.geonames.org/export/dump/cities500.zip"
RU_NAMES = Path(__file__).resolve().parents[2] / "data" / "places_ru.tsv.gz"
csv.field_size_limit(sys.maxsize)


class Command(BaseCommand):
    help = "Load birthplaces (GeoNames cities500) into the database."

    def add_arguments(self, parser):
        parser.add_argument("--source", default=URL, help="path or URL of cities500.zip")
        parser.add_argument("--if-empty", action="store_true")

    def handle(self, *args, source=URL, if_empty=False, **opts):
        if if_empty and GeoPlace.objects.exists():
            return
        ru: dict[int, str] = {}
        with gzip.open(RU_NAMES, "rt", encoding="utf-8") as f:
            for line in f:
                code, ru_name = line.rstrip("\n").split("\t", 1)
                ru[int(code)] = ru_name
        # the fixed GeoNames https URL or the operator's own file
        raw = urllib.request.urlopen(source, timeout=120).read() if source.startswith("https://") else Path(source).read_bytes()  # noqa: S310
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            text = z.read(next(n for n in z.namelist() if n.endswith(".txt"))).decode("utf-8")
        rows = []
        for c in csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE):
            gid, local, ascii_name = int(c[0]), c[1], c[2] or c[1]
            name = ru.get(gid, local)
            rows.append(
                GeoPlace(
                    id=gid,
                    name=name[:200],
                    name_en=ascii_name[:200],
                    country=c[8],
                    lat=float(c[4]),
                    lon=float(c[5]),
                    tz=c[17],
                    population=int(c[14] or 0),
                    key=search_key(name)[:200],
                    key_en=search_key(ascii_name)[:200],
                )
            )
        with transaction.atomic():
            GeoPlace.objects.all().delete()
            GeoPlace.objects.bulk_create(rows, batch_size=5000)
        self.stdout.write(self.style.SUCCESS(f"{len(rows)} places, {sum(r.id in ru for r in rows)} with Russian names"))
