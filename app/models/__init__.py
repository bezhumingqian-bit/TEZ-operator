"""SQLAlchemy ORM 模型。"""

from app.models.base import Base
from app.models.contact import Category, Contact, EscalationPath, Responsibility
from app.models.knowledge import FAQ, KnowledgeArticle, PlatformLink

__all__ = [
    "Base",
    "Contact", "Category", "Responsibility", "EscalationPath",
    "KnowledgeArticle", "FAQ", "PlatformLink",
]
