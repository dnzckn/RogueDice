"""Pygame-based pixel art game UI."""

import pygame
import sys
from typing import Optional, List, Tuple
from dataclasses import dataclass

from ..services.game_service import GameService, TurnResult
from ..components.board_square import BoardSquareComponent
from ..components.item import ItemComponent
from ..models.enums import SquareType, Rarity


# Colors (pixel art palette)
COLORS = {
    'black': (0, 0, 0),
    'white': (255, 255, 255),
    'gray': (128, 128, 128),
    'dark_gray': (64, 64, 64),
    'red': (255, 0, 0),
    'green': (0, 255, 0),
    'blue': (0, 120, 255),
    'yellow': (255, 255, 0),
    'orange': (255, 165, 0),
    'purple': (138, 43, 226),
    'pink': (255, 0, 128),
    'brown': (139, 69, 19),
    'dark_green': (0, 100, 0),
    'light_blue': (135, 206, 235),
    'gold': (255, 215, 0),
}

SQUARE_COLORS = {
    SquareType.EMPTY: (100, 150, 100),
    SquareType.MONSTER: (150, 50, 50),
    SquareType.ITEM: (50, 100, 150),
    SquareType.CORNER_START: (100, 200, 100),
    SquareType.CORNER_SHOP: (200, 200, 100),
    SquareType.CORNER_REST: (100, 100, 200),
    SquareType.CORNER_BOSS: (200, 50, 50),
    SquareType.SPECIAL: (150, 100, 200),
}


class GameUI:
    """Main game UI using pygame."""

    WINDOW_WIDTH = 1024
    WINDOW_HEIGHT = 768
    BOARD_SIZE = 500
    SQUARE_SIZE = 45
    FPS = 60

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("RogueDice")

        self.screen = pygame.display.set_mode(
            (self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        )
        self.clock = pygame.time.Clock()
        self.font_large = pygame.font.Font(None, 36)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)

        self.game = GameService()
        self.game.new_game()

        self.last_turn_result: Optional[TurnResult] = None
        self.combat_log: List[str] = []
        self.message_log: List[str] = ["Welcome to RogueDice!", "Press SPACE to roll dice."]

        self.state = "playing"  # playing, game_over, inventory

    def run(self) -> None:
        """Main game loop."""
        running = True

        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_keydown(event)

            # Update
            self._update()

            # Draw
            self._draw()

            pygame.display.flip()
            self.clock.tick(self.FPS)

        pygame.quit()
        sys.exit()

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        """Handle key press events."""
        if self.state == "game_over":
            if event.key == pygame.K_r:
                self.game.new_game()
                self.state = "playing"
                self.message_log = ["New game started!", "Press SPACE to roll dice."]
            return

        if self.state == "inventory":
            if event.key == pygame.K_ESCAPE or event.key == pygame.K_i:
                self.state = "playing"
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
                               pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9):
                # Equip item at index
                index = event.key - pygame.K_1
                inventory = self.game.get_player_inventory()
                if index < len(inventory):
                    self.game.equip_item(inventory[index])
                    self.message_log.append("Item equipped!")
            return

        # Playing state
        if event.key == pygame.K_SPACE:
            self._take_turn()
        elif event.key == pygame.K_i:
            self.state = "inventory"
        elif event.key == pygame.K_r and self.game.is_game_over:
            self.game.new_game()
            self.state = "playing"

    def _take_turn(self) -> None:
        """Execute a turn."""
        if self.game.is_game_over:
            return

        result = self.game.take_turn()
        self.last_turn_result = result

        # Update message log
        d1, d2, total = result.move_result.dice
        self.message_log.append(f"Rolled {d1}+{d2}={total}!")
        self.message_log.append(
            f"Moved to square {result.move_result.to_square}"
        )

        if result.combat_result:
            self.combat_log = result.combat_result.log[-10:]  # Last 10 lines
            if result.combat_result.victory:
                self.message_log.append(
                    f"Victory! +{result.gold_earned} gold"
                )
                if result.item_received and result.item_component:
                    self.message_log.append(
                        f"Found: {result.item_component.name}"
                    )
            else:
                self.message_log.append("Defeated!")
        elif result.item_received and result.item_component:
            self.message_log.append(f"Found: {result.item_component.name}")
        elif result.healed:
            self.message_log.append("Rested at inn. HP restored!")

        if result.monsters_spawned:
            self.message_log.append(
                f"New monsters appeared on {len(result.monsters_spawned)} squares!"
            )

        if result.game_over:
            self.state = "game_over"
            self.message_log.append("GAME OVER! Press R to restart.")

        # Trim log
        self.message_log = self.message_log[-8:]

    def _update(self) -> None:
        """Update game state."""
        pass

    def _draw(self) -> None:
        """Draw the game."""
        self.screen.fill(COLORS['dark_gray'])

        self._draw_board()
        self._draw_player_stats()
        self._draw_message_log()

        if self.combat_log:
            self._draw_combat_log()

        if self.state == "inventory":
            self._draw_inventory()
        elif self.state == "game_over":
            self._draw_game_over()

    def _draw_board(self) -> None:
        """Draw the game board."""
        # Board position
        board_x = 50
        board_y = 50
        board_inner = self.BOARD_SIZE - 2 * self.SQUARE_SIZE

        # Draw board background
        pygame.draw.rect(
            self.screen,
            COLORS['brown'],
            (board_x, board_y, self.BOARD_SIZE, self.BOARD_SIZE)
        )
        pygame.draw.rect(
            self.screen,
            COLORS['dark_green'],
            (
                board_x + self.SQUARE_SIZE,
                board_y + self.SQUARE_SIZE,
                board_inner,
                board_inner
            )
        )

        # Get squares and player position
        squares = self.game.get_board_squares()
        player_pos = self.game.get_player_position()

        # Draw squares
        for square in squares:
            x, y = self._get_square_position(square.index, board_x, board_y)
            self._draw_square(x, y, square, square.index == player_pos)

        # Draw board title
        title = self.font_medium.render("ROGUE DICE", True, COLORS['gold'])
        self.screen.blit(title, (board_x + self.BOARD_SIZE // 2 - 50, board_y + self.BOARD_SIZE // 2 - 10))

    def _get_square_position(
        self, index: int, board_x: int, board_y: int
    ) -> Tuple[int, int]:
        """Get pixel position for a square index."""
        # Board layout: 10 squares per side
        # Top: 0-10 (left to right)
        # Right: 11-19 (top to bottom)
        # Bottom: 20-30 (right to left)
        # Left: 31-39 (bottom to top)

        if index <= 10:  # Top row
            x = board_x + index * self.SQUARE_SIZE
            y = board_y
        elif index <= 19:  # Right column
            x = board_x + self.BOARD_SIZE - self.SQUARE_SIZE
            y = board_y + (index - 10) * self.SQUARE_SIZE
        elif index <= 30:  # Bottom row
            x = board_x + self.BOARD_SIZE - (index - 20) * self.SQUARE_SIZE - self.SQUARE_SIZE
            y = board_y + self.BOARD_SIZE - self.SQUARE_SIZE
        else:  # Left column
            x = board_x
            y = board_y + self.BOARD_SIZE - (index - 30) * self.SQUARE_SIZE - self.SQUARE_SIZE

        return (x, y)

    def _draw_square(
        self,
        x: int,
        y: int,
        square: BoardSquareComponent,
        has_player: bool,
    ) -> None:
        """Draw a single board square."""
        color = SQUARE_COLORS.get(square.square_type, COLORS['gray'])

        # Darken if has monster
        if square.has_monster:
            color = (max(0, color[0] - 30), max(0, color[1] - 30), max(0, color[2] - 30))

        pygame.draw.rect(
            self.screen,
            color,
            (x, y, self.SQUARE_SIZE - 2, self.SQUARE_SIZE - 2)
        )
        pygame.draw.rect(
            self.screen,
            COLORS['black'],
            (x, y, self.SQUARE_SIZE - 2, self.SQUARE_SIZE - 2),
            1
        )

        # Draw index number
        num_text = self.font_small.render(str(square.index), True, COLORS['white'])
        self.screen.blit(num_text, (x + 2, y + 2))

        # Draw monster indicator
        if square.has_monster:
            pygame.draw.circle(
                self.screen,
                COLORS['red'],
                (x + self.SQUARE_SIZE // 2, y + self.SQUARE_SIZE // 2),
                8
            )

        # Draw item indicator
        if square.square_type == SquareType.ITEM:
            pygame.draw.circle(
                self.screen,
                COLORS['gold'],
                (x + self.SQUARE_SIZE // 2, y + self.SQUARE_SIZE // 2),
                6
            )

        # Draw player
        if has_player:
            pygame.draw.circle(
                self.screen,
                COLORS['blue'],
                (x + self.SQUARE_SIZE // 2, y + self.SQUARE_SIZE // 2),
                12
            )
            pygame.draw.circle(
                self.screen,
                COLORS['white'],
                (x + self.SQUARE_SIZE // 2, y + self.SQUARE_SIZE // 2),
                12,
                2
            )

    def _draw_player_stats(self) -> None:
        """Draw player stats panel."""
        x = 580
        y = 50

        # Background
        pygame.draw.rect(
            self.screen,
            COLORS['dark_gray'],
            (x, y, 400, 200)
        )
        pygame.draw.rect(
            self.screen,
            COLORS['white'],
            (x, y, 400, 200),
            2
        )

        # Get stats
        stats = self.game.get_player_stats()
        player = self.game.get_player_data()

        if not stats or not player:
            return

        # Title
        title = self.font_large.render(player.name, True, COLORS['gold'])
        self.screen.blit(title, (x + 10, y + 10))

        # HP Bar
        hp_text = self.font_medium.render(
            f"HP: {stats.current_hp}/{stats.max_hp}", True, COLORS['white']
        )
        self.screen.blit(hp_text, (x + 10, y + 50))

        # HP bar visual
        bar_width = 200
        bar_height = 15
        hp_percent = stats.current_hp / stats.max_hp
        pygame.draw.rect(
            self.screen,
            COLORS['dark_gray'],
            (x + 10, y + 75, bar_width, bar_height)
        )
        pygame.draw.rect(
            self.screen,
            COLORS['green'] if hp_percent > 0.5 else COLORS['red'],
            (x + 10, y + 75, int(bar_width * hp_percent), bar_height)
        )

        # Stats
        stats_text = [
            f"Round: {player.current_round}",
            f"Gold: {player.gold}",
            f"ATK: {stats.base_damage:.1f}  SPD: {stats.attack_speed:.1f}",
            f"DEF: {stats.defense}  CRIT: {stats.crit_chance*100:.0f}%",
            f"Kills: {player.monsters_killed}  Items: {player.items_collected}",
        ]

        for i, text in enumerate(stats_text):
            rendered = self.font_medium.render(text, True, COLORS['white'])
            self.screen.blit(rendered, (x + 10, y + 100 + i * 20))

        # Controls hint
        hint = self.font_small.render(
            "[SPACE] Roll  [I] Inventory", True, COLORS['gray']
        )
        self.screen.blit(hint, (x + 10, y + 210))

    def _draw_message_log(self) -> None:
        """Draw message log."""
        x = 580
        y = 280

        pygame.draw.rect(
            self.screen,
            COLORS['black'],
            (x, y, 400, 180)
        )
        pygame.draw.rect(
            self.screen,
            COLORS['white'],
            (x, y, 400, 180),
            1
        )

        title = self.font_medium.render("Messages", True, COLORS['gold'])
        self.screen.blit(title, (x + 10, y + 5))

        for i, msg in enumerate(self.message_log[-7:]):
            text = self.font_small.render(msg, True, COLORS['white'])
            self.screen.blit(text, (x + 10, y + 30 + i * 20))

    def _draw_combat_log(self) -> None:
        """Draw combat log."""
        x = 580
        y = 480

        pygame.draw.rect(
            self.screen,
            (30, 30, 30),
            (x, y, 400, 250)
        )
        pygame.draw.rect(
            self.screen,
            COLORS['red'],
            (x, y, 400, 250),
            2
        )

        title = self.font_medium.render("Combat Log", True, COLORS['red'])
        self.screen.blit(title, (x + 10, y + 5))

        for i, msg in enumerate(self.combat_log[-10:]):
            # Truncate long messages
            if len(msg) > 50:
                msg = msg[:47] + "..."
            text = self.font_small.render(msg, True, COLORS['white'])
            self.screen.blit(text, (x + 10, y + 30 + i * 20))

    def _draw_inventory(self) -> None:
        """Draw inventory overlay."""
        # Semi-transparent overlay
        overlay = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        overlay.fill(COLORS['black'])
        overlay.set_alpha(200)
        self.screen.blit(overlay, (0, 0))

        # Inventory window
        x, y = 200, 100
        w, h = 600, 500

        pygame.draw.rect(self.screen, COLORS['dark_gray'], (x, y, w, h))
        pygame.draw.rect(self.screen, COLORS['gold'], (x, y, w, h), 3)

        title = self.font_large.render("INVENTORY", True, COLORS['gold'])
        self.screen.blit(title, (x + w // 2 - 70, y + 20))

        # Equipment section
        equipment = self.game.get_player_equipment()
        eq_y = y + 70

        self.screen.blit(
            self.font_medium.render("Equipment:", True, COLORS['white']),
            (x + 20, eq_y)
        )

        if equipment:
            slots = [
                ("Weapon", equipment.weapon),
                ("Armor", equipment.armor),
                ("Ring 1", equipment.jewelry_slots[0] if equipment.jewelry_slots else None),
                ("Ring 2", equipment.jewelry_slots[1] if len(equipment.jewelry_slots) > 1 else None),
                ("Ring 3", equipment.jewelry_slots[2] if len(equipment.jewelry_slots) > 2 else None),
            ]

            for i, (slot_name, item_id) in enumerate(slots):
                item_name = "Empty"
                color = COLORS['gray']
                if item_id:
                    item = self.game.get_item(item_id)
                    if item:
                        item_name = item.name
                        color = item.rarity.color

                text = self.font_small.render(f"{slot_name}: {item_name}", True, color)
                self.screen.blit(text, (x + 40, eq_y + 25 + i * 22))

        # Inventory items
        inv_y = eq_y + 160
        self.screen.blit(
            self.font_medium.render("Items (press 1-9 to equip):", True, COLORS['white']),
            (x + 20, inv_y)
        )

        inventory = self.game.get_player_inventory()
        for i, item_id in enumerate(inventory[:9]):
            item = self.game.get_item(item_id)
            if item:
                color = item.rarity.color
                text = self.font_small.render(
                    f"{i + 1}. {item.name}",
                    True,
                    color
                )
                self.screen.blit(text, (x + 40, inv_y + 25 + i * 22))

        # Close hint
        hint = self.font_medium.render(
            "Press I or ESC to close",
            True,
            COLORS['gray']
        )
        self.screen.blit(hint, (x + w // 2 - 80, y + h - 40))

    def _draw_game_over(self) -> None:
        """Draw game over screen."""
        overlay = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        overlay.fill(COLORS['black'])
        overlay.set_alpha(180)
        self.screen.blit(overlay, (0, 0))

        text = self.font_large.render("GAME OVER", True, COLORS['red'])
        self.screen.blit(
            text,
            (self.WINDOW_WIDTH // 2 - 80, self.WINDOW_HEIGHT // 2 - 50)
        )

        player = self.game.get_player_data()
        if player:
            stats_text = f"Round: {player.current_round}  Kills: {player.monsters_killed}  Gold: {player.gold}"
            text2 = self.font_medium.render(stats_text, True, COLORS['white'])
            self.screen.blit(
                text2,
                (self.WINDOW_WIDTH // 2 - 120, self.WINDOW_HEIGHT // 2)
            )

        restart = self.font_medium.render("Press R to restart", True, COLORS['gold'])
        self.screen.blit(
            restart,
            (self.WINDOW_WIDTH // 2 - 80, self.WINDOW_HEIGHT // 2 + 50)
        )
