"""Phase 3: the "outbox" of files the laptop has queued to send to a phone."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class OutboxItem:
    item_id: str
    name: str
    rel_path: str  # path relative to the outbox root, used as the zip entry name
    size: int
    path: Path
    group: str | None = None  # folder name when this file was part of a dropped folder
    added_at: float = field(default_factory=time.time)


class OutboxManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.items: dict[str, OutboxItem] = {}

    def add(self, name: str, rel_path: str, size: int, path: Path, group: str | None) -> OutboxItem:
        item = OutboxItem(
            item_id=uuid.uuid4().hex, name=name, rel_path=rel_path, size=size, path=path, group=group
        )
        self.items[item.item_id] = item
        return item

    def get(self, item_id: str) -> OutboxItem | None:
        return self.items.get(item_id)

    def items_in_group(self, group: str) -> list[OutboxItem]:
        return [i for i in self.items.values() if i.group == group]

    def listing(self) -> dict:
        files = [i for i in self.items.values() if i.group is None]
        groups: dict[str, list[OutboxItem]] = {}
        for item in self.items.values():
            if item.group:
                groups.setdefault(item.group, []).append(item)
        return {
            "files": [self._serialize(i) for i in sorted(files, key=lambda i: i.added_at)],
            "folders": [
                {
                    "group": group,
                    "size": sum(i.size for i in items),
                    "count": len(items),
                }
                for group, items in groups.items()
            ],
        }

    @staticmethod
    def _serialize(item: OutboxItem) -> dict:
        return {
            "item_id": item.item_id,
            "name": item.name,
            "size": item.size,
            "group": item.group,
        }

    def remove(self, item_id: str) -> bool:
        item = self.items.pop(item_id, None)
        if item is None:
            return False
        item.path.unlink(missing_ok=True)
        return True
