from django.db import migrations


def seed(apps, schema_editor):
    """Texts reread for machine patterns: composite advice per planet (no sentence repeats in one report), the «Важно…»
    formula, telegraphic dashes and decorative «не X, а Y» rewritten; same meaning, same placeholders."""
    from apps.knowledge.seeding import load_seed

    load_seed(apps.get_model("knowledge", "KnowledgeBlock"))


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0008_quiz_icons")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
