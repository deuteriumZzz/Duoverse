from .base import *  # noqa: F403

DEBUG = True

# drafts are visible in dev so content can be reviewed in context; prod shows published only
KB_ALLOWED_STATUSES = ["draft", "reviewed", "published"]
