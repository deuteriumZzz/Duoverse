from django.db import migrations


def seed(apps, schema_editor):
    """Each arcana in love, the arcana of the union, the four link types, all 253 arcana pairs, and every number the
    report shows (life path, name, pair, personal year, how two numbers relate)."""
    from apps.knowledge.seeding import load_seed

    load_seed(apps.get_model("knowledge", "KnowledgeBlock"))


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0011_neutral_quotes")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
