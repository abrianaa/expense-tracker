# Smart Expense & Budget Analyzer

A desktop app to log expenses, categorize them, track budgets and visualize spending with charts.

**Tech stack:** Python · Tkinter · SQLite · Pandas · Matplotlib

| Member | Role | Module |
|--------|------|--------|
| A | Frontend – Tkinter GUI (forms, Treeview, layouts) | `gui.py` *(to be added)* |
| **B** | **Backend – SQLite database & CRUD** | **`database.py`** ✅ |
| C | Data processing (Pandas) & Matplotlib charts | `analysis.py` *(to be added)* |

This repository currently contains the **backend (Member B)**: the database layer, tests and sample-data generator.

---

## Project structure

```
smart-expense-analyzer/
├── database.py          # SQLite layer: all CRUD, search, analytics, budgets, CSV
├── seed_data.py         # Fill the DB with realistic sample data
├── tests/
│   └── test_database.py # 40 unit tests (unittest, no extra dependencies)
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

## Getting started

```bash
git clone https://github.com/<your-username>/smart-expense-analyzer.git
cd smart-expense-analyzer

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python seed_data.py --reset      # optional: create sample data
python database.py               # quick smoke test
python -m unittest discover -s tests -v
```

The database file is created automatically at `data/expenses.db` (git-ignored).

## Database schema

```sql
CREATE TABLE expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    NOT NULL,              -- 'YYYY-MM-DD'
    category    TEXT    NOT NULL,
    amount      REAL    NOT NULL CHECK (amount > 0),
    description TEXT    DEFAULT ''
);

-- Optional extra for the "Budget" feature
CREATE TABLE budgets (
    category      TEXT PRIMARY KEY,
    monthly_limit REAL NOT NULL CHECK (monthly_limit > 0)
);
```

Dates are stored as ISO text (`YYYY-MM-DD`), so sorting and range queries work correctly with plain string comparison.

## API reference

```python
from database import ExpenseDatabase
db = ExpenseDatabase()          # or ExpenseDatabase(":memory:") for tests
```

Every row is returned as a `dict`:
`{'id': 1, 'date': '2025-01-15', 'category': 'Food', 'amount': 250.5, 'description': 'Lunch'}`

### CRUD

| Method | Description |
|--------|-------------|
| `add_expense(date, category, amount, description="")` | Insert; returns the new `id` |
| `get_expense(expense_id)` | One row (raises `RecordNotFoundError`) |
| `get_all_expenses(order_by="date", descending=True)` | All rows |
| `update_expense(expense_id, date=None, category=None, amount=None, description=None)` | Updates only the fields you pass |
| `delete_expense(expense_id)` | Delete one |
| `delete_many([ids])` | Delete several (multi-select); returns count |
| `clear_all_expenses()` | Delete everything; returns count |
| `count_expenses()` | Number of rows |

### Search & filter

```python
db.search_expenses(
    start_date="2025-01-01", end_date="2025-01-31",
    category="Food", keyword="pizza",
    min_amount=100, max_amount=1000,
    order_by="amount", descending=True,
)
```
All filters are optional and combine with AND. `get_categories()` returns the distinct categories in use.

### Analytics (for Member C)

| Method | Returns |
|--------|---------|
| `get_total_spent(start_date=None, end_date=None)` | `float` |
| `get_category_totals(start_date=None, end_date=None)` | `[{'category': 'Rent', 'total': 12000.0}, ...]` |
| `get_monthly_totals()` | `[{'month': '2025-01', 'total': 8450.5}, ...]` |
| `get_expenses_df(**filters)` | pandas `DataFrame` (`date` is `datetime64`) |

### Budgets (optional feature)

| Method | Description |
|--------|-------------|
| `set_budget(category, monthly_limit)` | Create or update |
| `get_budgets()` | All budgets |
| `delete_budget(category)` | Remove one |
| `get_budget_status("2025-01")` | Per category: `limit`, `spent`, `remaining`, `percent_used`, `over_budget` |

### CSV

| Method | Description |
|--------|-------------|
| `export_to_csv(path)` | Write all expenses to CSV |
| `import_from_csv(path)` | Needs `date`, `category`, `amount` columns; all-or-nothing |

### Validation & errors

Input is validated and cleaned automatically:

- **date** → must be a real date; normalised to `YYYY-MM-DD` (`datetime.date` objects are accepted too)
- **category** → trimmed and Title-Cased (`"  food "` → `"Food"`) so there are no duplicates like `food` / `Food`
- **amount** → must be a number > 0, rounded to 2 decimals (`"1,200.50"` works)
- **description** → optional, max 200 characters

All errors inherit from `DatabaseError`:

| Exception | When |
|-----------|------|
| `ValidationError` | Bad date / amount / category, etc. (also a `ValueError`) |
| `RecordNotFoundError` | The `id` or category doesn't exist |
| `DatabaseError` | Any other database / file problem |

## Integration guide

### For Member A – Tkinter

```python
import tkinter as tk
from tkinter import ttk, messagebox
from database import ExpenseDatabase, ValidationError, DEFAULT_CATEGORIES

db = ExpenseDatabase()

# Fill a Treeview
def refresh_table(tree):
    tree.delete(*tree.get_children())
    for row in db.get_all_expenses():
        tree.insert("", "end", iid=row["id"],
                    values=(row["id"], row["date"], row["category"],
                            f"{row['amount']:.2f}", row["description"]))

# Add button handler
def on_add(date_var, cat_var, amount_var, desc_var, tree):
    try:
        db.add_expense(date_var.get(), cat_var.get(), amount_var.get(), desc_var.get())
    except ValidationError as err:
        messagebox.showerror("Invalid input", str(err))
        return
    refresh_table(tree)

# Delete button handler (supports multi-select)
def on_delete(tree):
    ids = [int(i) for i in tree.selection()]
    if ids and messagebox.askyesno("Confirm", f"Delete {len(ids)} expense(s)?"):
        db.delete_many(ids)
        refresh_table(tree)

# Category dropdown:  ttk.Combobox(values=DEFAULT_CATEGORIES)
# Close the DB when the window closes:  root.protocol("WM_DELETE_WINDOW", lambda: (db.close(), root.destroy()))
```

Tip: store the expense `id` as the Treeview `iid` (as above) so you can always recover it from `tree.selection()`.

### For Member C – Pandas & Matplotlib

```python
import matplotlib.pyplot as plt
from database import ExpenseDatabase

db = ExpenseDatabase()

# Pie chart from SQL aggregates
totals = db.get_category_totals()
plt.pie([t["total"] for t in totals], labels=[t["category"] for t in totals], autopct="%1.1f%%")
plt.show()

# Or use a DataFrame for anything custom
df = db.get_expenses_df()
monthly = df.groupby(df["date"].dt.to_period("M"))["amount"].sum()
monthly.plot(kind="bar")
plt.show()
```

To embed a chart in Tkinter, use `FigureCanvasTkAgg` from `matplotlib.backends.backend_tkagg`.

## Team workflow (suggested)

- `main` is always working. Each member works on a branch: `feature/database`, `feature/gui`, `feature/charts`.
- Open a pull request and have a teammate review it before merging.
- **Do not change the function names or return formats in `database.py` without telling the team** – the GUI and charts depend on them.

## Design decisions (good for your viva)

- **Parameterized queries (`?`)** everywhere → protects against SQL injection. Only the `ORDER BY` column is interpolated, and it is checked against a whitelist.
- **Transactions** (`with self._conn:`) → every write commits on success and rolls back on error.
- **Validation lives in the backend**, not the GUI, so bad data can't enter no matter who calls the functions.
- **`CHECK (amount > 0)`** in the schema is a second line of defence behind Python validation.
- **Indexes on `date` and `category`** keep filtering and grouping fast as data grows.
- **Custom exceptions** let the GUI show friendly messages instead of crashing.
- **Aggregations in SQL** (`SUM`, `GROUP BY`) rather than in Python loops.

## License

MIT – see [LICENSE](LICENSE).
