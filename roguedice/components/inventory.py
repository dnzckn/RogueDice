"""Inventory component for storing items."""

from dataclasses import dataclass, field
from typing import List, Optional
from ..core.component import Component


@dataclass
class InventoryComponent(Component):
    """Items carried by an entity."""

    items: List[int] = field(default_factory=list)  # Entity IDs of items
    max_capacity: int = 20

    def add_item(self, item_id: int) -> bool:
        """Add item to inventory. Returns True if successful."""
        if len(self.items) < self.max_capacity:
            self.items.append(item_id)
            return True
        return False

    def remove_item(self, item_id: int) -> bool:
        """Remove item from inventory. Returns True if found."""
        if item_id in self.items:
            self.items.remove(item_id)
            return True
        return False

    def has_item(self, item_id: int) -> bool:
        """Check if item is in inventory."""
        return item_id in self.items

    @property
    def is_full(self) -> bool:
        """Check if inventory is full."""
        return len(self.items) >= self.max_capacity

    @property
    def space_remaining(self) -> int:
        """Get number of free slots."""
        return self.max_capacity - len(self.items)
