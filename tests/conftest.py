import pytest


@pytest.fixture(autouse=True)
def knowledge_seed(request):
    """Transactional tests flush tables between tests; reload the bundled knowledge seed when the test touches the DB."""
    if "django_db_setup" in request.fixturenames or request.node.get_closest_marker("django_db"):
        db = request.getfixturevalue("transactional_db" if request.node.get_closest_marker("django_db").kwargs.get("transaction") else "db")
        del db
        from apps.knowledge.models import KnowledgeBlock
        from apps.knowledge.seeding import load_seed

        if not KnowledgeBlock.objects.exists():
            load_seed(KnowledgeBlock)
