from django.db import migrations


def seed(apps, schema_editor):
    """93 pair-type and attachment/pattern texts cut to two or three sentences: same meaning, same placeholders."""
    from apps.knowledge.seeding import load_seed

    load_seed(apps.get_model("knowledge", "KnowledgeBlock"))


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0006_seed_status")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
