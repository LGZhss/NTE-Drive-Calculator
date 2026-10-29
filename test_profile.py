import time
import os
import json
import sqlite3
import cProfile
from src.services.blueprint_service import solve_blueprints_from_static
from src.storage.sqlite.static_game_data_dao import StaticGameDataDao

def main():
    dao = StaticGameDataDao()
    suits = dao.list_suits()
    suit_id = suits[0]["suit_id"]

    board_cells = [
        {"row_number": 1, "column_number": 1, "is_enabled": True},
        {"row_number": 1, "column_number": 2, "is_enabled": True},
        {"row_number": 1, "column_number": 3, "is_enabled": True},
        {"row_number": 1, "column_number": 4, "is_enabled": True},
        {"row_number": 1, "column_number": 5, "is_enabled": True},
        {"row_number": 2, "column_number": 1, "is_enabled": True},
        {"row_number": 2, "column_number": 2, "is_enabled": True},
        {"row_number": 2, "column_number": 3, "is_enabled": True},
        {"row_number": 2, "column_number": 4, "is_enabled": True},
        {"row_number": 2, "column_number": 5, "is_enabled": True},
        {"row_number": 3, "column_number": 1, "is_enabled": True},
        {"row_number": 3, "column_number": 2, "is_enabled": True},
        {"row_number": 3, "column_number": 3, "is_enabled": True},
        {"row_number": 3, "column_number": 4, "is_enabled": True},
        {"row_number": 3, "column_number": 5, "is_enabled": True},
        {"row_number": 4, "column_number": 1, "is_enabled": True},
        {"row_number": 4, "column_number": 2, "is_enabled": True},
        {"row_number": 4, "column_number": 3, "is_enabled": True},
        {"row_number": 4, "column_number": 4, "is_enabled": True},
        {"row_number": 4, "column_number": 5, "is_enabled": True},
    ]

    custom_chars = []
    for i in range(100):
        custom_chars.append({
            "character_id": 1000 + i,
            "name_zh": f"Char {i}",
            "target_suit_id": suit_id,
            "board_cells": board_cells
        })

    start = time.time()
    for _ in range(5):
        solve_blueprints_from_static(dao, custom_characters=custom_chars)
    end = time.time()
    print(f"Original Time: {end - start:.4f}s")

if __name__ == "__main__":
    main()
