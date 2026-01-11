"""RogueDice - A Roguelike Board Game.

Entry point for the game.
"""

from .ui import GameUI


def main():
    """Run the game."""
    ui = GameUI()
    ui.run()


if __name__ == "__main__":
    main()
