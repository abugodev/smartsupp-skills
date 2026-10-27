"""Command modules; each exposes OPS."""
from typing import List

from ..ops import Op
from . import agents, bots, contacts, conversations, files, messages, oauth, settings, statistics, tags, visitors

ALL_OPS = (
    list(agents.OPS) + list(bots.OPS) + list(contacts.OPS) + list(conversations.OPS) + list(files.OPS)
    + list(messages.OPS) + list(oauth.OPS) + list(settings.OPS) + list(statistics.OPS) + list(tags.OPS)
    + list(visitors.OPS)
)  # type: List[Op]
