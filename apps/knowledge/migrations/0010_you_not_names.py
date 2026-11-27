from django.db import migrations


def seed(apps, schema_editor):
    """«Аня и Миша похожи в главном» → «Вы похожи в главном»: 146 aspect texts and 9 pair insights speak to the pair, names
    stay only where it matters who does what; four questions to each other no longer depend on gender."""
    from apps.knowledge.seeding import load_seed

    load_seed(apps.get_model("knowledge", "KnowledgeBlock"))


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0009_humanized_texts")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
