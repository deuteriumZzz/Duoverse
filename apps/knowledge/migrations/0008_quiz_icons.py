from django.db import migrations


def seed(apps, schema_editor):
    """Every quiz gets its own icon (data.icon, a Lucide name) instead of one gem for all 52."""
    from apps.knowledge.seeding import load_seed

    load_seed(apps.get_model("knowledge", "KnowledgeBlock"))


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0007_shorter_texts")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
