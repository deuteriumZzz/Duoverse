from django.db import migrations


def seed(apps, schema_editor):
    """The seed loader now carries status too: Gottman's four horsemen (published in the seed long ago) and three
    habits stayed drafts in databases seeded earlier — invisible in production, which shows published blocks only."""
    from apps.knowledge.seeding import load_seed

    load_seed(apps.get_model("knowledge", "KnowledgeBlock"))


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0005_more_content")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
