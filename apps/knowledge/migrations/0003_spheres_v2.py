from django.db import migrations


def seed(apps, schema_editor):
    from apps.knowledge.seeding import load_seed

    load_seed(apps.get_model("knowledge", "KnowledgeBlock"))


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0002_seed_blocks")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
