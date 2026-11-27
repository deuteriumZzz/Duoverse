from django.db import migrations


def seed(apps, schema_editor):
    """Words in «…» are a phrase to say as is, so they can't be agreed by gender: «чтобы ты просто выслушал(а)» →
    «чтобы меня просто выслушали», and the same for four more phrases."""
    from apps.knowledge.seeding import load_seed

    load_seed(apps.get_model("knowledge", "KnowledgeBlock"))


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0010_you_not_names")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
