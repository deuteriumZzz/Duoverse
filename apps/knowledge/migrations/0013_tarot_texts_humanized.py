from django.db import migrations


def seed(apps, schema_editor):
    """Tarot and numbers texts in the same voice as the rest: no «гармония», «глубокий», «бережно», «энергия» on every
    line, no «не X, а Y», dashes only where Russian needs them (122 texts)."""
    from apps.knowledge.seeding import load_seed

    load_seed(apps.get_model("knowledge", "KnowledgeBlock"))


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0012_tarot_and_numbers")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
