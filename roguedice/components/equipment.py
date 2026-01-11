"""Equipment component for equipped items."""

from dataclasses import dataclass, field
from typing import List, Optional
from ..core.component import Component


@dataclass
class EquipmentComponent(Component):
    """Currently equipped items."""

    weapon: Optional[int] = None        # Entity ID
    armor: Optional[int] = None         # Entity ID
    jewelry_slots: List[Optional[int]] = field(
        default_factory=lambda: [None, None, None]  # 3 jewelry slots
    )

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

    def equip_jewelry(self, item_id: int, slot: int = 0) -> Optional[int]:
        """Equip jewelry to slot, return previously equipped jewelry ID if any."""
        if 0 <= slot < len(self.jewelry_slots):
            old = self.jewelry_slots[slot]
            self.jewelry_slots[slot] = item_id
            return old
        return None

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

    def unequip_jewelry(self, slot: int) -> Optional[int]:
        """Unequip and return jewelry ID from slot."""
        if 0 <= slot < len(self.jewelry_slots):
            old = self.jewelry_slots[slot]
            self.jewelry_slots[slot] = None
            return old
        return None

    def get_all_equipped(self) -> List[int]:
        """Get list of all equipped item IDs."""
        equipped = []
        if self.weapon is not None:
            equipped.append(self.weapon)
        if self.armor is not None:
            equipped.append(self.armor)
        for jewelry in self.jewelry_slots:
            if jewelry is not None:
                equipped.append(jewelry)
        return equipped
