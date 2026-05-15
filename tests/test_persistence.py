import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
import tempfile
from persistence import init_db, save_fighters, load_fighters, save_session, load_session, delete_session, save_to_slot, load_from_slot, list_saves, delete_save, export_save, import_save, SaveIncompatibleError
from generator import generate_fighter_pool
from promotion import create_promotions
from fighter import Fighter
from datetime import datetime
import utils


class TestPersistence(unittest.TestCase):

    def setUp(self):
        self._orig_db = os.environ.get("MMALIFE_DB", "")
        self.tmp_db = tempfile.mktemp(suffix=".db")
        os.environ["MMALIFE_DB"] = self.tmp_db
        from persistence import _conn
        import persistence
        persistence._conn = None
        init_db()

    def tearDown(self):
        if self._orig_db:
            os.environ["MMALIFE_DB"] = self._orig_db
        else:
            os.environ.pop("MMALIFE_DB", None)
        if os.path.exists(self.tmp_db):
            os.unlink(self.tmp_db)

    def test_save_load_fighter(self):
        f = Fighter("Test Person", 25, 170, "mma", "balanced",
                    nationality="American", home_region="California")
        f.wins = 10
        f.losses = 2
        f.rank = 5
        save_fighters([f])
        loaded = load_fighters()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].name, "Test Person")
        self.assertEqual(loaded[0].wins, 10)
        self.assertEqual(loaded[0].losses, 2)

    def test_save_load_session(self):
        sid = "test-session-1"
        session = {"fighter_name": "Test", "game_date": datetime(2025, 1, 1),
                   "some_data": [1, 2, 3], "_created": 12345}
        save_session(sid, session)
        loaded = load_session(sid)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["fighter_name"], "Test")
        self.assertEqual(loaded["some_data"], [1, 2, 3])

    def test_delete_session(self):
        sid = "test-session-2"
        save_session(sid, {"data": "test"})
        delete_session(sid)
        self.assertIsNone(load_session(sid))

    def test_generated_fighters_roundtrip(self):
        weight_classes = [wc["name"] for wc in utils.WEIGHT_CLASSES]
        promotions = create_promotions(weight_classes)
        fighters = generate_fighter_pool(promotions, 50)
        save_fighters(fighters)
        loaded = load_fighters()
        self.assertEqual(len(loaded), 50)
        for orig, loaded_f in zip(fighters, loaded):
            self.assertEqual(orig.name, loaded_f.name)
            self.assertEqual(orig.attributes, loaded_f.attributes)

    def test_session_pickle_complex(self):
        from training import TrainingSystem
        from career import CareerSystem
        from finance import FinancialSystem
        f = Fighter("Pickle Test", 25, 170, "mma", "balanced")
        sid = "complex-session"
        session = {
            "fighter": f,
            "career": CareerSystem(f),
            "training": TrainingSystem(f),
            "finance": FinancialSystem(f),
            "game_date": datetime(2025, 6, 1),
        }
        save_session(sid, session)
        loaded = load_session(sid)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["fighter"].name, "Pickle Test")
        self.assertIsNotNone(loaded["career"])
        self.assertIsNotNone(loaded["training"])

    # --- Save Slot Tests ---

    def test_save_load_slot_roundtrip(self):
        from training import TrainingSystem
        from career import CareerSystem
        from finance import FinancialSystem
        f = Fighter("Slot Test", 25, 170, "mma", "balanced")
        f.wins = 5
        f.losses = 1
        sid = "slot-test-user"
        session = {
            "fighter": f,
            "career": CareerSystem(f),
            "training": TrainingSystem(f),
            "finance": FinancialSystem(f),
            "game_date": datetime(2025, 6, 15),
            "current_promotion": None,
            "current_fight": None,
            "fight_started": False,
        }
        world_data = ([], [], None, [])
        save_to_slot(sid, 0, "Test Auto", session, world_data)
        saved_saves = list_saves(sid)
        self.assertEqual(len(saved_saves), 1)
        self.assertEqual(saved_saves[0]["fighter_name"], "Slot Test")
        self.assertEqual(saved_saves[0]["record"], "5-1-0")
        loaded_session, loaded_world = load_from_slot(sid, 0)
        self.assertEqual(loaded_session["fighter"].name, "Slot Test")
        self.assertEqual(loaded_session["fighter"].wins, 5)
        self.assertIsNotNone(loaded_session["career"])

    def test_multiple_save_slots(self):
        f1 = Fighter("Fighter One", 25, 170, "mma", "balanced")
        f2 = Fighter("Fighter Two", 30, 185, "boxing", "balanced")
        sid = "multi-slot-user"
        session1 = {"fighter": f1, "game_date": datetime(2025, 1, 1)}
        session2 = {"fighter": f2, "game_date": datetime(2025, 6, 1)}
        world_data = ([], [], None, [])
        save_to_slot(sid, 0, "Slot 0", session1, world_data)
        save_to_slot(sid, 1, "Slot 1", session2, world_data)
        saved_saves = list_saves(sid)
        self.assertEqual(len(saved_saves), 2)
        slot_map = {s["slot_index"]: s for s in saved_saves}
        self.assertEqual(slot_map[0]["fighter_name"], "Fighter One")
        self.assertEqual(slot_map[1]["fighter_name"], "Fighter Two")
        loaded_0, _ = load_from_slot(sid, 0)
        loaded_1, _ = load_from_slot(sid, 1)
        self.assertEqual(loaded_0["fighter"].name, "Fighter One")
        self.assertEqual(loaded_1["fighter"].name, "Fighter Two")

    def test_delete_save_slot(self):
        f = Fighter("Delete Me", 25, 170, "mma", "balanced")
        sid = "delete-test"
        session = {"fighter": f, "game_date": datetime(2025, 1, 1)}
        world_data = ([], [], None, [])
        save_to_slot(sid, 0, "Test", session, world_data)
        self.assertEqual(len(list_saves(sid)), 1)
        delete_save(sid, 0)
        self.assertEqual(len(list_saves(sid)), 0)
        result = load_from_slot(sid, 0)
        self.assertIsNone(result)

    def test_in_fight_flag(self):
        f = Fighter("In Fight", 25, 170, "mma", "balanced")
        sid = "infight-test"
        session_in_fight = {
            "fighter": f,
            "current_fight": {"some": "data"},
            "game_date": datetime(2025, 1, 1),
        }
        world_data = ([], [], None, [])
        save_to_slot(sid, 0, "In Fight", session_in_fight, world_data)
        saved = list_saves(sid)
        self.assertEqual(saved[0]["in_fight"], 1)

    def test_export_import_roundtrip(self):
        from training import TrainingSystem
        f = Fighter("Export Test", 25, 170, "mma", "balanced")
        f.wins = 10
        sid = "export-test-user"
        session = {
            "fighter": f,
            "training": TrainingSystem(f),
            "game_date": datetime(2025, 3, 15),
            "current_fight": None,
            "fight_started": False,
        }
        world_data = ([], ["dummy_fighter"], None, [])
        save_to_slot(sid, 0, "Export Test", session, world_data)
        export_data = export_save(sid, 0)
        self.assertIsNotNone(export_data)
        self.assertEqual(export_data["fighter_name"], "Export Test")
        self.assertEqual(export_data["format_version"], 1)
        # Import to slot 1
        import_save(sid, 1, export_data)
        saved = list_saves(sid)
        self.assertEqual(len(saved), 2)
        loaded, _ = load_from_slot(sid, 1)
        self.assertEqual(loaded["fighter"].name, "Export Test")
        self.assertEqual(loaded["fighter"].wins, 10)

    def test_version_mismatch_rejected(self):
        import pickle
        import sqlite3
        from persistence import _get_conn, SAVE_FORMAT_VERSION
        f = Fighter("Version Test", 25, 170, "mma", "balanced")
        sid = "version-test-user"
        conn = _get_conn()
        bad_blob = pickle.dumps({"v": 99, "data": {"fighter": f}})
        conn.execute(
            "INSERT OR REPLACE INTO player_saves "
            "(save_id, slot_index, display_name, fighter_name, record, promotion_name,"
            " game_date, in_fight, save_format_version, player_state, world_snapshot,"
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?, julianday('now'), julianday('now'))",
            (f"{sid}_slot_0", 0, "Bad Version", "Version Test", "0-0-0",
             "None", "2025-01-01", 0, 99, bad_blob, bad_blob)
        )
        conn.commit()
        with self.assertRaises(SaveIncompatibleError):
            load_from_slot(sid, 0)

    def test_corrupt_save_handled(self):
        import sqlite3
        from persistence import _get_conn
        sid = "corrupt-test-user"
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO player_saves "
            "(save_id, slot_index, display_name, fighter_name, record, promotion_name,"
            " game_date, in_fight, save_format_version, player_state, world_snapshot,"
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?, julianday('now'), julianday('now'))",
            (f"{sid}_slot_0", 0, "Corrupt", "Corrupt", "0-0-0",
             "None", "2025-01-01", 0, 1, b"garbage", b"garbage")
        )
        conn.commit()
        with self.assertRaises(Exception):
            load_from_slot(sid, 0)
