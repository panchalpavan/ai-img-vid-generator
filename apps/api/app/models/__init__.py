"""SQLModel table definitions.

Importing every model module from this package registers their tables on
`SQLModel.metadata`. Alembic's env.py imports this package as a whole so it
sees every model at autogenerate time.

When adding a new model, add it to this file's re-exports.
"""

from app.models.credit_transaction import CreditTransaction, TransactionType
from app.models.generation import Generation, GenerationStatus
from app.models.profile import Profile
from app.models.user import User

__all__ = [
    "CreditTransaction",
    "Generation",
    "GenerationStatus",
    "Profile",
    "TransactionType",
    "User",
]
