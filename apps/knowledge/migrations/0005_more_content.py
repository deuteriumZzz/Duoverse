from django.db import migrations


def seed(apps, schema_editor):
    """A year of content: 52 quizzes, eight habits per sphere, holiday questions — into databases seeded before."""
    from apps.knowledge.seeding import load_seed

    load_seed(apps.get_model("knowledge", "KnowledgeBlock"))


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0004_sun_sign_interpretations")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
