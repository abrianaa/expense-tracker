"""
database.py - SQLite backend for the Smart Expense & Budget Analyzer.

Owner: Member B (Backend / SQLite)

This module is the single place in the project that talks to SQLite.
Member A (Tkinter GUI) and Member C (Pandas / Matplotlib) should import
``ExpenseDatabase`` from here and never write raw SQL themselves.

Agreed schema (table ``expenses``):
    id          INTEGER  primary key, auto-increment
    date        TEXT     stored as 'YYYY-MM-DD'
    category    TEXT     e.g. 'Food', 'Transport'
    amount      REAL     always > 0
    description TEXT     optional note

Quick example:
    from database import ExpenseDatabase

    db = ExpenseDatabase()                       # opens data/expenses.db
    new_id = db.add_expense("2025-01-15", "Food", 250.50, "Lunch")
    rows = db.get_all_expenses()                 # list of dicts
    db.close()

Or, with automatic cleanup:
    with ExpenseDatabase() as db:
        db.add_expense("2025-01-15", "Food", 250.50)
"""

from __future__ import annotations

import csv
import math
import sqlite3
from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "expenses.db"
DATE_FORMAT = "%Y-%m-%d"
MONTH_FORMAT = "%Y-%m"

MAX_CATEGORY_LENGTH = 50
MAX_DESCRIPTION_LENGTH = 200

# Suggested categories. Member A can use these to fill a Combobox.
# Users can still type any category they like.
DEFAULT_CATEGORIES = [
    "Food",
    "Transport",
    "Rent",
    "Utilities",
    "Shopping",
    "Entertainment",
    "Health",
    "Education",
    "Other",
]

# Columns that are safe to use in ORDER BY (prevents SQL injection).
_SORTABLE_COLUMNS = {"id", "date", "category", "amount", "description"}

DateLike = Union[str, _date, datetime]


# --------------------------------------------------------------------------- #
# Custom exceptions (so the GUI can show friendly messages)
# --------------------------------------------------------------------------- #

class DatabaseError(Exception):
    """Base class for all errors raised by this module."""


class ValidationError(DatabaseError, ValueError):
    """Raised when user-supplied data is invalid (bad date, negative amount...)."""


class RecordNotFoundError(DatabaseError):
    """Raised when an expense / budget with the given key does not exist."""


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #

def validate_date(value: DateLike) -> str:
    """Return the date normalised to 'YYYY-MM-DD' or raise ValidationError."""
    if isinstance(value, datetime):
        return value.strftime(DATE_FORMAT)
    if isinstance(value, _date):
        return value.strftime(DATE_FORMAT)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Date is required (format: YYYY-MM-DD).")
    try:
        return datetime.strptime(value.strip(), DATE_FORMAT).strftime(DATE_FORMAT)
    except ValueError:
        raise ValidationError(
            f"Invalid date '{value}'. Use the format YYYY-MM-DD (e.g. 2025-01-31)."
        ) from None


def validate_month(value: str) -> str:
    """Return a month string normalised to 'YYYY-MM' or raise ValidationError."""
    try:
        return datetime.strptime(str(value).strip(), MONTH_FORMAT).strftime(MONTH_FORMAT)
    except ValueError:
        raise ValidationError(
            f"Invalid month '{value}'. Use the format YYYY-MM (e.g. 2025-01)."
        ) from None


def validate_category(value: str) -> str:
    """Strip, collapse whitespace and Title-Case the category."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Category is required.")
    cleaned = " ".join(value.split()).title()
    if len(cleaned) > MAX_CATEGORY_LENGTH:
        raise ValidationError(f"Category must be at most {MAX_CATEGORY_LENGTH} characters.")
    return cleaned


def validate_amount(value: Any) -> float:
    """Convert to a positive float rounded to 2 decimals or raise ValidationError."""
    if isinstance(value, bool):  # bool is a subclass of int; reject it explicitly
        raise ValidationError("Amount must be a number.")
    try:
        number = float(str(value).replace(",", "").strip()) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"Amount '{value}' is not a valid number.") from None
    if math.isnan(number) or math.isinf(number):
        raise ValidationError("Amount must be a finite number.")
    if number <= 0:
        raise ValidationError("Amount must be greater than 0.")
    return round(number, 2)


def validate_description(value: Optional[str]) -> str:
    """Description is optional; trim and length-check it."""
    if value is None:
        return ""
    cleaned = str(value).strip()
    if len(cleaned) > MAX_DESCRIPTION_LENGTH:
        raise ValidationError(
            f"Description must be at most {MAX_DESCRIPTION_LENGTH} characters."
        )
    return cleaned


# --------------------------------------------------------------------------- #
# Main class
# --------------------------------------------------------------------------- #

class ExpenseDatabase:
    """Thin, safe wrapper around an SQLite database of expenses.

    All rows are returned as plain ``dict`` objects, e.g.
    ``{'id': 1, 'date': '2025-01-15', 'category': 'Food',
       'amount': 250.5, 'description': 'Lunch'}``.
    """

    def __init__(self, db_path: Union[str, Path] = DEFAULT_DB_PATH) -> None:
        """Open (and create if needed) the database.

        Pass ``":memory:"`` for a throw-away database (used in the unit tests).
        """
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

        try:
            self._conn = sqlite3.connect(self.db_path)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not open database '{self.db_path}': {exc}") from exc

        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    # ------------------------------------------------------------------ #
    # Setup / teardown
    # ------------------------------------------------------------------ #

    def _create_tables(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    date        TEXT    NOT NULL,
                    category    TEXT    NOT NULL,
                    amount      REAL    NOT NULL CHECK (amount > 0),
                    description TEXT    DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_expenses_date
                    ON expenses (date);
                CREATE INDEX IF NOT EXISTS idx_expenses_category
                    ON expenses (category);

                -- Optional extra for the "Budget" half of the project.
                CREATE TABLE IF NOT EXISTS budgets (
                    category      TEXT PRIMARY KEY,
                    monthly_limit REAL NOT NULL CHECK (monthly_limit > 0)
                );
                """
            )

    def close(self) -> None:
        """Close the database connection. Call this when the app exits."""
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "ExpenseDatabase":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #

    def add_expense(
        self,
        date: DateLike,
        category: str,
        amount: Any,
        description: Optional[str] = "",
    ) -> int:
        """Insert a new expense and return its new ``id``."""
        values = (
            validate_date(date),
            validate_category(category),
            validate_amount(amount),
            validate_description(description),
        )
        try:
            with self._conn:
                cursor = self._conn.execute(
                    "INSERT INTO expenses (date, category, amount, description) "
                    "VALUES (?, ?, ?, ?)",
                    values,
                )
            return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to add expense: {exc}") from exc

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #

    def get_expense(self, expense_id: int) -> dict:
        """Return one expense by id or raise RecordNotFoundError."""
        row = self._conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"No expense found with id {expense_id}.")
        return dict(row)

    def get_all_expenses(
        self, order_by: str = "date", descending: bool = True
    ) -> list[dict]:
        """Return every expense. Newest first by default."""
        return self.search_expenses(order_by=order_by, descending=descending)

    def search_expenses(
        self,
        start_date: Optional[DateLike] = None,
        end_date: Optional[DateLike] = None,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        min_amount: Optional[Any] = None,
        max_amount: Optional[Any] = None,
        order_by: str = "date",
        descending: bool = True,
    ) -> list[dict]:
        """Filter expenses. Every argument is optional and they combine with AND.

        keyword matches against the description *and* the category
        (case-insensitive, partial match).
        """
        if order_by not in _SORTABLE_COLUMNS:
            raise ValidationError(
                f"Cannot sort by '{order_by}'. Choose from: {sorted(_SORTABLE_COLUMNS)}"
            )

        clauses: list[str] = []
        params: list[Any] = []

        if start_date is not None:
            clauses.append("date >= ?")
            params.append(validate_date(start_date))
        if end_date is not None:
            clauses.append("date <= ?")
            params.append(validate_date(end_date))
        if category:
            clauses.append("category = ? COLLATE NOCASE")
            params.append(validate_category(category))
        if keyword:
            like = f"%{keyword.strip()}%"
            clauses.append("(description LIKE ? OR category LIKE ?)")
            params.extend([like, like])
        if min_amount is not None:
            clauses.append("amount >= ?")
            params.append(validate_amount(min_amount))
        if max_amount is not None:
            clauses.append("amount <= ?")
            params.append(validate_amount(max_amount))

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        direction = "DESC" if descending else "ASC"
        # `order_by` is whitelisted above, so the f-string is safe here.
        sql = f"SELECT * FROM expenses {where} ORDER BY {order_by} {direction}, id {direction}"

        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_categories(self) -> list[str]:
        """Distinct categories currently in use (alphabetical)."""
        rows = self._conn.execute(
            "SELECT DISTINCT category FROM expenses ORDER BY category"
        ).fetchall()
        return [r["category"] for r in rows]

    def count_expenses(self) -> int:
        """Total number of expense rows."""
        return int(self._conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0])

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #

    def update_expense(
        self,
        expense_id: int,
        date: Optional[DateLike] = None,
        category: Optional[str] = None,
        amount: Optional[Any] = None,
        description: Optional[str] = None,
    ) -> None:
        """Update only the fields you pass in (others stay unchanged)."""
        fields: list[str] = []
        params: list[Any] = []

        if date is not None:
            fields.append("date = ?")
            params.append(validate_date(date))
        if category is not None:
            fields.append("category = ?")
            params.append(validate_category(category))
        if amount is not None:
            fields.append("amount = ?")
            params.append(validate_amount(amount))
        if description is not None:
            fields.append("description = ?")
            params.append(validate_description(description))

        if not fields:
            raise ValidationError("Nothing to update: pass at least one field.")

        params.append(expense_id)
        try:
            with self._conn:
                cursor = self._conn.execute(
                    f"UPDATE expenses SET {', '.join(fields)} WHERE id = ?", params
                )
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to update expense: {exc}") from exc

        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"No expense found with id {expense_id}.")

    # ------------------------------------------------------------------ #
    # DELETE
    # ------------------------------------------------------------------ #

    def delete_expense(self, expense_id: int) -> None:
        """Delete one expense by id."""
        try:
            with self._conn:
                cursor = self._conn.execute(
                    "DELETE FROM expenses WHERE id = ?", (expense_id,)
                )
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to delete expense: {exc}") from exc
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"No expense found with id {expense_id}.")

    def delete_many(self, expense_ids: list[int]) -> int:
        """Delete several expenses at once (e.g. multi-select in Treeview).

        Returns the number of rows actually deleted.
        """
        if not expense_ids:
            return 0
        placeholders = ",".join("?" for _ in expense_ids)
        try:
            with self._conn:
                cursor = self._conn.execute(
                    f"DELETE FROM expenses WHERE id IN ({placeholders})",
                    list(expense_ids),
                )
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to delete expenses: {exc}") from exc
        return cursor.rowcount

    def clear_all_expenses(self) -> int:
        """Delete ALL expenses. Returns how many rows were removed."""
        with self._conn:
            cursor = self._conn.execute("DELETE FROM expenses")
        return cursor.rowcount

    # ------------------------------------------------------------------ #
    # ANALYTICS (aggregates done in SQL - fast and simple)
    # ------------------------------------------------------------------ #

    def get_total_spent(
        self,
        start_date: Optional[DateLike] = None,
        end_date: Optional[DateLike] = None,
    ) -> float:
        """Sum of all amounts, optionally within a date range."""
        clauses, params = self._date_range_clause(start_date, end_date)
        sql = f"SELECT COALESCE(SUM(amount), 0) FROM expenses {clauses}"
        return round(float(self._conn.execute(sql, params).fetchone()[0]), 2)

    def get_category_totals(
        self,
        start_date: Optional[DateLike] = None,
        end_date: Optional[DateLike] = None,
    ) -> list[dict]:
        """Total per category, biggest first. Perfect for a pie / bar chart.

        Example: [{'category': 'Rent', 'total': 12000.0}, ...]
        """
        clauses, params = self._date_range_clause(start_date, end_date)
        sql = (
            "SELECT category, ROUND(SUM(amount), 2) AS total "
            f"FROM expenses {clauses} GROUP BY category ORDER BY total DESC"
        )
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def get_monthly_totals(self) -> list[dict]:
        """Total per month, oldest first. Perfect for a line / bar chart.

        Example: [{'month': '2025-01', 'total': 8450.5}, ...]
        """
        rows = self._conn.execute(
            "SELECT substr(date, 1, 7) AS month, ROUND(SUM(amount), 2) AS total "
            "FROM expenses GROUP BY month ORDER BY month"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_expenses_df(self, **filters: Any):
        """Return expenses as a pandas DataFrame (for Member C).

        Accepts the same keyword filters as ``search_expenses``.
        The ``date`` column is converted to ``datetime64``.
        """
        try:
            import pandas as pd  # imported lazily so the DB works without pandas
        except ImportError as exc:  # pragma: no cover
            raise DatabaseError(
                "pandas is required for get_expenses_df(). Run: pip install pandas"
            ) from exc

        columns = ["id", "date", "category", "amount", "description"]
        rows = self.search_expenses(**filters)
        df = pd.DataFrame(rows, columns=columns)
        df["date"] = pd.to_datetime(df["date"])
        return df

    @staticmethod
    def _date_range_clause(
        start_date: Optional[DateLike], end_date: Optional[DateLike]
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if start_date is not None:
            clauses.append("date >= ?")
            params.append(validate_date(start_date))
        if end_date is not None:
            clauses.append("date <= ?")
            params.append(validate_date(end_date))
        return (f"WHERE {' AND '.join(clauses)}" if clauses else ""), params

    # ------------------------------------------------------------------ #
    # BUDGETS (optional extra feature)
    # ------------------------------------------------------------------ #

    def set_budget(self, category: str, monthly_limit: Any) -> None:
        """Create or update the monthly budget for a category."""
        cat = validate_category(category)
        limit = validate_amount(monthly_limit)
        with self._conn:
            self._conn.execute(
                "INSERT INTO budgets (category, monthly_limit) VALUES (?, ?) "
                "ON CONFLICT(category) DO UPDATE SET monthly_limit = excluded.monthly_limit",
                (cat, limit),
            )

    def get_budgets(self) -> list[dict]:
        """All budgets, alphabetical."""
        rows = self._conn.execute(
            "SELECT category, monthly_limit FROM budgets ORDER BY category"
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_budget(self, category: str) -> None:
        """Remove the budget for a category."""
        cat = validate_category(category)
        with self._conn:
            cursor = self._conn.execute("DELETE FROM budgets WHERE category = ?", (cat,))
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"No budget set for category '{cat}'.")

    def get_budget_status(self, month: Optional[str] = None) -> list[dict]:
        """Compare actual spending with budgets for one month.

        ``month`` is 'YYYY-MM'; defaults to the current month.
        Each item looks like:
            {'category': 'Food', 'limit': 5000.0, 'spent': 3200.0,
             'remaining': 1800.0, 'percent_used': 64.0, 'over_budget': False}
        """
        month = validate_month(month) if month else datetime.now().strftime(MONTH_FORMAT)
        rows = self._conn.execute(
            """
            SELECT b.category,
                   b.monthly_limit AS "limit",
                   COALESCE(SUM(e.amount), 0) AS spent
            FROM budgets b
            LEFT JOIN expenses e
                   ON e.category = b.category AND substr(e.date, 1, 7) = ?
            GROUP BY b.category, b.monthly_limit
            ORDER BY b.category
            """,
            (month,),
        ).fetchall()

        result = []
        for r in rows:
            limit, spent = float(r["limit"]), round(float(r["spent"]), 2)
            result.append(
                {
                    "category": r["category"],
                    "limit": limit,
                    "spent": spent,
                    "remaining": round(limit - spent, 2),
                    "percent_used": round(spent / limit * 100, 1),
                    "over_budget": spent > limit,
                }
            )
        return result

    # ------------------------------------------------------------------ #
    # CSV import / export
    # ------------------------------------------------------------------ #

    _CSV_COLUMNS = ["id", "date", "category", "amount", "description"]

    def export_to_csv(self, file_path: Union[str, Path]) -> int:
        """Write all expenses to a CSV file. Returns the number of rows written."""
        rows = self.get_all_expenses(order_by="date", descending=False)
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=self._CSV_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
        except OSError as exc:
            raise DatabaseError(f"Could not write CSV file: {exc}") from exc
        return len(rows)

    def import_from_csv(self, file_path: Union[str, Path]) -> int:
        """Import expenses from a CSV (needs date, category, amount columns).

        The import is all-or-nothing: if any row is invalid, nothing is saved
        and a ValidationError tells you which line was wrong.
        Returns the number of rows imported.
        """
        try:
            with open(file_path, newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                headers = {h.strip().lower() for h in (reader.fieldnames or [])}
                missing = {"date", "category", "amount"} - headers
                if missing:
                    raise ValidationError(
                        f"CSV is missing required column(s): {', '.join(sorted(missing))}"
                    )

                prepared = []
                for line_no, raw in enumerate(reader, start=2):  # line 1 is the header
                    row = {k.strip().lower(): v for k, v in raw.items() if k}
                    try:
                        prepared.append(
                            (
                                validate_date(row["date"]),
                                validate_category(row["category"]),
                                validate_amount(row["amount"]),
                                validate_description(row.get("description", "")),
                            )
                        )
                    except ValidationError as exc:
                        raise ValidationError(f"CSV line {line_no}: {exc}") from exc
        except OSError as exc:
            raise DatabaseError(f"Could not read CSV file: {exc}") from exc

        with self._conn:  # one transaction: commit all or roll back all
            self._conn.executemany(
                "INSERT INTO expenses (date, category, amount, description) "
                "VALUES (?, ?, ?, ?)",
                prepared,
            )
        return len(prepared)


# --------------------------------------------------------------------------- #
# Run this file directly for a quick smoke test:  python database.py
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    with ExpenseDatabase(":memory:") as demo:
        demo.add_expense("2025-01-05", "food", 250.5, "Lunch with friends")
        demo.add_expense("2025-01-06", "Transport", 80, "Metro card")
        demo.add_expense("2025-02-01", "Rent", 12000, "February rent")

        print("All expenses:")
        for item in demo.get_all_expenses():
            print("  ", item)

        print("\nTotals by category:", demo.get_category_totals())
        print("Monthly totals:    ", demo.get_monthly_totals())
        print("Total spent:       ", demo.get_total_spent())
