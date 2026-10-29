import time
import os
import json
import sqlite3
from src.services.blueprint_service import solve_blueprints_from_static
from src.storage.sqlite.static_game_data_dao import StaticGameDataDao

def main():
    dao = StaticGameDataDao()

    # We want to benchmark the solve_blueprints_from_static with custom characters
    # First get a valid target_suit_id
    suits = dao.list_suits()
    if not suits:
        print("No suits found in db, skipping benchmark")
        return

    suit_id = suits[0]["suit_id"]

    # 20 valid cells for board_cells
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

    # Create lots of custom characters
    custom_chars = []
    for i in range(100):
        custom_chars.append({
            "character_id": 1000 + i,
            "name_zh": f"Char {i}",
            "target_suit_id": suit_id,
            "board_cells": board_cells
        })

    start_time = time.time()
    for _ in range(5): # Run multiple times
        solve_blueprints_from_static(dao, custom_characters=custom_chars)
    end_time = time.time()

    print(f"Time taken for 5 runs of 100 characters: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    main()
