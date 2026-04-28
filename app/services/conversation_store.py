from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class ConversationStore:
    _items_by_session: dict[str, list[dict[str, object]]] = field(default_factory=dict)

    def create_session_id(self) -> str:
        session_id = str(uuid4())
        self._items_by_session.setdefault(session_id, [])
        return session_id

    def get_items(self, session_id: str) -> list[dict[str, object]]:
        return list(self._items_by_session.get(session_id, []))

    def append_items(self, session_id: str, items: list[dict[str, object]]) -> None:
        self._items_by_session.setdefault(session_id, []).extend(items)


conversation_store = ConversationStore()
