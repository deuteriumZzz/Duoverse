from django.db import migrations


def split(apps, schema_editor):
    """A sphere's one line is now the first sentence of its own reading, not a line shared by several spheres.
    Reports saved before keep that reading whole as story[1]: split it the same way, so «Власть и контроль» stops
    saying «ссоритесь редко» and the opened sphere doesn't repeat its own line."""
    StoredReport = apps.get_model("compatibility", "StoredReport")
    for r in StoredReport.objects.exclude(snapshot=None).iterator():
        changed = False
        for s in (r.snapshot or {}).get("spheres") or []:
            story = s.get("story") or []
            if len(story) == 2 and story[1]:
                first, _, rest = story[1].partition(". ")
                s["summary"] = first if first.endswith(".") else f"{first}."
                s["story"] = [story[0]] + ([rest] if rest else [])
                changed = True
        if changed:
            r.save(update_fields=["snapshot"])


class Migration(migrations.Migration):
    dependencies = [("compatibility", "0019_person_gender")]

    operations = [migrations.RunPython(split, migrations.RunPython.noop)]
