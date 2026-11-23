"""Run with: python -m unittest discover -s tests -v"""
import tempfile
import unittest
from pathlib import Path
import database as db


class TestDemoDatabase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_db = db.DB_PATH
        self.original_data = db.DATA_DIR
        db.DATA_DIR = Path(self.temp.name)
        db.DB_PATH = db.DATA_DIR / "test.sqlite3"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.original_db
        db.DATA_DIR = self.original_data
        self.temp.cleanup()

    def test_seeded_catalog_and_search(self):
        self.assertEqual(len(db.books()), 8)
        self.assertEqual(db.books("Frankenstein")[0]["author"], "Mary Shelley")
        self.assertGreater(len(db.categories()), 2)

    def test_register_and_fine_suspension(self):
        uid = db.create_user("TestCustomer")
        self.assertEqual(db.get_user(user_id=uid)["role"], "RC")
        book = db.books("Sherlock")[0]
        result = db.purchase(uid, book["id"])
        self.assertFalse(result["suspended"])
        book2 = db.books("Frankenstein")[0]
        result = db.purchase(uid, book2["id"])
        self.assertTrue(result["suspended"])
        self.assertEqual(result["fine_cents"], 100)
        self.assertTrue(db.get_user(user_id=uid)["suspended"])
        db.admin_reopen(uid, 2000)
        self.assertFalse(db.get_user(user_id=uid)["suspended"])

    def test_face_metadata(self):
        uid = db.create_user("StudentRC")
        db.set_face_profile(uid, "/fake/face.npz")
        self.assertEqual(db.get_face_profile(uid), "/fake/face.npz")

    def test_review_verification(self):
        uid = db.create_user("Reviewer")
        book = db.books("Oz")[0]
        db.purchase(uid, book["id"])
        self.assertFalse(db.add_review(book["id"], uid, "", 5, "Wonderful book"))
        rating, count = db.avg_rating(book["id"])
        self.assertEqual((rating, count), (5.0, 1))


if __name__ == "__main__":
    unittest.main()
