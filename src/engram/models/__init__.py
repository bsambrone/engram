"""Models package — re-exports Base and all model classes for Alembic discovery."""

from engram.models.auth import AccessToken
from engram.models.base import Base
from engram.models.connector import DataExport, IngestionJob
from engram.models.identity import (
    Belief,
    BeliefMemory,
    IdentityProfile,
    IdentitySnapshot,
    Preference,
    PreferenceMemory,
    StyleProfile,
)
from engram.models.memory import Memory, MemoryPerson, MemoryTopic, Person, Topic
from engram.models.photo import Photo, PhotoPerson
from engram.models.social import LifeEvent, Location, Relationship

__all__ = [
    "Base",
    # memory
    "Memory",
    "Topic",
    "MemoryTopic",
    "Person",
    "MemoryPerson",
    # identity
    "IdentityProfile",
    "Belief",
    "BeliefMemory",
    "Preference",
    "PreferenceMemory",
    "StyleProfile",
    "IdentitySnapshot",
    # connector
    "DataExport",
    "IngestionJob",
    # auth
    "AccessToken",
    # photo
    "Photo",
    "PhotoPerson",
    # social
    "Relationship",
    "Location",
    "LifeEvent",
]
