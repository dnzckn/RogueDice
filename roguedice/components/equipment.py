"""Equipment component for equipped items."""

from dataclasses import dataclass, field
from typing import List, Optional
from ..core.component import Component


@dataclass
class EquipmentComponent(Component):
    """Currently equipped items - one slot per type."""

    weapon: Optional[int] = None   # Entity ID
    armor: Optional[int] = None    # Entity ID
    ring: Optional[int] = None     # Entity ID (single ring slot)

    def equip_weapon(self, item_id: int) -> Optional[int]:
        """Equip weapon, return previously equipped weapon ID if any."""
        old = self.weapon
        self.weapon = item_id
        return old

    def equip_armor(self, item_id: int) -> Optional[int]:
        """Equip armor, return previously equipped armor ID if any."""
        old = self.armor
        self.armor = item_id
        return old

    def equip_ring(self, item_id: int) -> Optional[int]:
        """Equip ring, return previously equipped ring ID if any."""
        old = self.ring
        self.ring = item_id
        return old

    def unequip_weapon(self) -> Optional[int]:
        """Unequip and return weapon ID."""
        old = self.weapon
        self.weapon = None
        return old

    def unequip_armor(self) -> Optional[int]:
        """Unequip and return armor ID."""
        old = self.armor
        self.armor = None
        return old

    def unequip_ring(self) -> Optional[int]:
        """Unequip and return ring ID."""
        old = self.ring
        self.ring = None
        return old

    def get_all_equipped(self) -> List[int]:
        """Get list of all equipped item IDs."""
        equipped = []
        if self.weapon is not None:
            equipped.append(self.weapon)
        if self.armor is not None:
            equipped.append(self.armor)
        if self.ring is not None:
            equipped.append(self.ring)
        return equipped
