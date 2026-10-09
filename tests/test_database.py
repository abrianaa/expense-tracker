"""
Unit tests for database.py

Run from the project root:
    python -m unittest discover -s tests -v
"""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import (  # noqa: E402
    ExpenseDatabase,
    RecordNotFoundError,
    ValidationError,
)


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.db = ExpenseDatabase(":memory:")

    def tearDown(self):
        self.db.close()


class TestCreateAndRead(BaseTest):
    def test_add_returns_incrementing_ids(self):
        first = self.db.add_expense("2025-01-01", "Food", 100)
        second = self.db.add_expense("2025-01-02", "Food", 200)
        self.assertEqual(second, first + 1)

    def test_get_expense_returns_correct_data(self):
        new_id = self.db.add_expense("2025-01-15", "food", "250.50", "  Lunch  ")
        row = self.db.get_expense(new_id)
        self.assertEqual(row["date"], "2025-01-15")
        self.assertEqual(row["category"], "Food")  # normalised
        self.assertEqual(row["amount"], 250.5)
        self.assertEqual(row["description"], "Lunch")  # trimmed

    def test_date_is_normalised(self):
        new_id = self.db.add_expense("2025-1-5", "Food", 10)
        self.assertEqual(self.db.get_expense(new_id)["date"], "2025-01-05")

    def test_get_missing_expense_raises(self):
        with self.assertRaises(RecordNotFoundError):
            self.db.get_expense(999)

    def test_get_all_default_order_is_newest_first(self):
        self.db.add_expense("2025-01-01", "Food", 10)
        self.db.add_expense("2025-03-01", "Food", 10)
        self.db.add_expense("2025-02-01", "Food", 10)
        dates = [r["date"] for r in self.db.get_all_expenses()]
        self.assertEqual(dates, ["2025-03-01", "2025-02-01", "2025-01-01"])

    def test_invalid_order_by_rejected(self):
        with self.assertRaises(ValidationError):
            self.db.get_all_expenses(order_by="amount; DROP TABLE expenses")


class TestValidation(BaseTest):
    def test_bad_dates(self):
        for bad in ["", "15-01-2025", "2025-13-01", "2025-02-30", "hello", None]:
            with self.subTest(date=bad), self.assertRaises(ValidationError):
                self.db.add_expense(bad, "Food", 10)

    def test_bad_amounts(self):
        for bad in [0, -5, "abc", None, float("nan"), float("inf"), True]:
            with self.subTest(amount=bad), self.assertRaises(ValidationError):
                self.db.add_expense("2025-01-01", "Food", bad)

    def test_amount_with_commas_is_accepted(self):
        new_id = self.db.add_expense("2025-01-01", "Rent", "12,000.50")
        self.assertEqual(self.db.get_expense(new_id)["amount"], 12000.5)

    def test_empty_category_rejected(self):
        with self.assertRaises(ValidationError):
            self.db.add_expense("2025-01-01", "   ", 10)

    def test_too_long_description_rejected(self):
        with self.assertRaises(ValidationError):
            self.db.add_expense("2025-01-01", "Food", 10, "x" * 201)

    def test_sql_injection_is_stored_as_plain_text(self):
        evil = "'); DROP TABLE expenses; --"
        new_id = self.db.add_expense("2025-01-01", "Food", 10, evil)
        self.assertEqual(self.db.get_expense(new_id)["description"], evil)
        self.assertEqual(self.db.count_expenses(), 1)


class TestUpdateAndDelete(BaseTest):
    def setUp(self):
        super().setUp()
        self.eid = self.db.add_expense("2025-01-01", "Food", 100, "Old")

    def test_partial_update_keeps_other_fields(self):
        self.db.update_expense(self.eid, amount=150)
        row = self.db.get_expense(self.eid)
        self.assertEqual(row["amount"], 150)
        self.assertEqual(row["description"], "Old")
        self.assertEqual(row["category"], "Food")

    def test_update_all_fields(self):
        self.db.update_expense(
            self.eid, date="2025-02-02", category="rent", amount=999, description="New"
        )
        row = self.db.get_expense(self.eid)
        self.assertEqual(
            (row["date"], row["category"], row["amount"], row["description"]),
            ("2025-02-02", "Rent", 999, "New"),
        )

    def test_update_with_no_fields_raises(self):
        with self.assertRaises(ValidationError):
            self.db.update_expense(self.eid)

    def test_update_missing_id_raises(self):
        with self.assertRaises(RecordNotFoundError):
            self.db.update_expense(999, amount=5)

    def test_delete(self):
        self.db.delete_expense(self.eid)
        self.assertEqual(self.db.count_expenses(), 0)

    def test_delete_missing_raises(self):
        with self.assertRaises(RecordNotFoundError):
            self.db.delete_expense(999)

    def test_delete_many(self):
        a = self.db.add_expense("2025-01-02", "Food", 1)
        b = self.db.add_expense("2025-01-03", "Food", 1)
        self.assertEqual(self.db.delete_many([a, b, 12345]), 2)
        self.assertEqual(self.db.count_expenses(), 1)

    def test_clear_all(self):
        self.db.add_expense("2025-01-02", "Food", 1)
        self.assertEqual(self.db.clear_all_expenses(), 2)
        self.assertEqual(self.db.count_expenses(), 0)


class TestSearchAndAnalytics(BaseTest):
    def setUp(self):
        super().setUp()
        self.db.add_expense("2025-01-05", "Food", 200, "Pizza night")
        self.db.add_expense("2025-01-20", "Transport", 50, "Bus pass")
        self.db.add_expense("2025-02-03", "Food", 300, "Groceries")
        self.db.add_expense("2025-02-10", "Rent", 10000, "Feb rent")

    def test_filter_by_category_case_insensitive(self):
        self.assertEqual(len(self.db.search_expenses(category="food")), 2)

    def test_filter_by_date_range(self):
        rows = self.db.search_expenses(start_date="2025-01-10", end_date="2025-02-05")
        self.assertEqual(len(rows), 2)

    def test_filter_by_keyword(self):
        rows = self.db.search_expenses(keyword="pizza")
        self.assertEqual(len(rows), 1)

    def test_filter_by_amount_range(self):
        rows = self.db.search_expenses(min_amount=100, max_amount=500)
        self.assertEqual({r["amount"] for r in rows}, {200, 300})

    def test_combined_filters(self):
        rows = self.db.search_expenses(category="Food", start_date="2025-02-01")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["description"], "Groceries")

    def test_total_spent(self):
        self.assertEqual(self.db.get_total_spent(), 10550)
        self.assertEqual(self.db.get_total_spent("2025-01-01", "2025-01-31"), 250)

    def test_total_spent_empty_range_is_zero(self):
        self.assertEqual(self.db.get_total_spent("2030-01-01", "2030-12-31"), 0)

    def test_category_totals_sorted_desc(self):
        totals = self.db.get_category_totals()
        self.assertEqual(totals[0], {"category": "Rent", "total": 10000.0})
        self.assertEqual(totals[1], {"category": "Food", "total": 500.0})

    def test_monthly_totals(self):
        self.assertEqual(
            self.db.get_monthly_totals(),
            [{"month": "2025-01", "total": 250.0}, {"month": "2025-02", "total": 10300.0}],
        )

    def test_get_categories(self):
        self.assertEqual(self.db.get_categories(), ["Food", "Rent", "Transport"])

    def test_dataframe(self):
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas not installed")
        df = self.db.get_expenses_df()
        self.assertEqual(len(df), 4)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df["date"]))
        self.assertEqual(list(df.columns), ["id", "date", "category", "amount", "description"])

    def test_empty_dataframe_has_columns(self):
        try:
            import pandas  # noqa: F401
        except ImportError:
            self.skipTest("pandas not installed")
        df = self.db.get_expenses_df(category="Nothing")
        self.assertTrue(df.empty)
        self.assertIn("amount", df.columns)


class TestBudgets(BaseTest):
    def test_budget_status(self):
        self.db.set_budget("Food", 500)
        self.db.set_budget("Transport", 100)
        self.db.add_expense("2025-01-05", "Food", 400)
        self.db.add_expense("2025-01-06", "Food", 200)
        self.db.add_expense("2025-02-01", "Food", 999)  # other month, ignored

        status = {s["category"]: s for s in self.db.get_budget_status("2025-01")}
        self.assertEqual(status["Food"]["spent"], 600)
        self.assertTrue(status["Food"]["over_budget"])
        self.assertEqual(status["Food"]["remaining"], -100)
        self.assertEqual(status["Food"]["percent_used"], 120.0)
        self.assertEqual(status["Transport"]["spent"], 0)
        self.assertFalse(status["Transport"]["over_budget"])

    def test_set_budget_twice_updates(self):
        self.db.set_budget("Food", 500)
        self.db.set_budget("food", 800)
        self.assertEqual(self.db.get_budgets(), [{"category": "Food", "monthly_limit": 800.0}])

    def test_delete_budget(self):
        self.db.set_budget("Food", 500)
        self.db.delete_budget("Food")
        self.assertEqual(self.db.get_budgets(), [])
        with self.assertRaises(RecordNotFoundError):
            self.db.delete_budget("Food")

    def test_bad_month(self):
        with self.assertRaises(ValidationError):
            self.db.get_budget_status("January")


class TestCsv(BaseTest):
    def test_round_trip(self):
        self.db.add_expense("2025-01-05", "Food", 200, "Pizza, extra cheese")
        self.db.add_expense("2025-01-06", "Rent", 10000)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.csv"
            self.assertEqual(self.db.export_to_csv(path), 2)

            other = ExpenseDatabase(":memory:")
            self.assertEqual(other.import_from_csv(path), 2)
            descriptions = {r["description"] for r in other.get_all_expenses()}
            self.assertIn("Pizza, extra cheese", descriptions)
            other.close()

    def test_import_is_all_or_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["date", "category", "amount", "description"])
                writer.writerow(["2025-01-01", "Food", "100", "ok"])
                writer.writerow(["not-a-date", "Food", "100", "bad"])
            with self.assertRaises(ValidationError) as ctx:
                self.db.import_from_csv(path)
            self.assertIn("line 3", str(ctx.exception))
        self.assertEqual(self.db.count_expenses(), 0)

    def test_import_missing_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nocols.csv"
            path.write_text("foo,bar\n1,2\n", encoding="utf-8")
            with self.assertRaises(ValidationError):
                self.db.import_from_csv(path)


class TestPersistence(unittest.TestCase):
    def test_data_survives_reopening(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "test.db"  # sub-folder is auto-created
            with ExpenseDatabase(path) as db:
                db.add_expense("2025-01-01", "Food", 10)
            with ExpenseDatabase(path) as db:
                self.assertEqual(db.count_expenses(), 1)


if __name__ == "__main__":
    unittest.main()
