"""
seed_data.py - fill the database with realistic sample data.

Useful so Member A can test the Treeview and Member C can test the charts
without typing in hundreds of expenses by hand.

Usage:
    python seed_data.py              # add 150 random expenses (last 6 months)
    python seed_data.py --reset      # wipe existing expenses first
    python seed_data.py --count 300  # choose how many rows to create
"""

import argparse
import random
from datetime import date, timedelta

from database import ExpenseDatabase

# category -> (min amount, max amount, sample descriptions)
SAMPLE_DATA = {
    "Food": (50, 800, ["Lunch", "Dinner", "Groceries", "Coffee", "Snacks", "Street food"]),
    "Transport": (20, 500, ["Bus ticket", "Metro recharge", "Auto rickshaw", "Fuel", "Cab ride"]),
    "Rent": (8000, 12000, ["Monthly rent"]),
    "Utilities": (200, 2000, ["Electricity bill", "Water bill", "Internet", "Mobile recharge"]),
    "Shopping": (200, 5000, ["Clothes", "Shoes", "Electronics", "Books", "Gift"]),
    "Entertainment": (100, 1500, ["Movie", "Netflix", "Concert", "Games", "Outing"]),
    "Health": (100, 3000, ["Pharmacy", "Doctor visit", "Gym", "Dental"]),
    "Education": (200, 4000, ["Stationery", "Course fee", "Printouts", "Textbook"]),
    "Other": (50, 1000, ["Miscellaneous", "Donation", "Repairs"]),
}

# Weighted so everyday categories show up more than rare ones.
WEIGHTS = {
    "Food": 30, "Transport": 20, "Rent": 0, "Utilities": 8, "Shopping": 10,
    "Entertainment": 10, "Health": 5, "Education": 5, "Other": 7,
}


def seed(db: ExpenseDatabase, count: int, months: int = 6) -> None:
    today = date.today()
    start = today - timedelta(days=30 * months)
    span_days = (today - start).days

    categories = list(WEIGHTS)
    weights = list(WEIGHTS.values())

    for _ in range(count):
        category = random.choices(categories, weights=weights, k=1)[0]
        low, high, descriptions = SAMPLE_DATA[category]
        when = start + timedelta(days=random.randint(0, span_days))
        amount = round(random.uniform(low, high), 2)
        db.add_expense(when, category, amount, random.choice(descriptions))

    # One rent payment on the 1st of every month in range.
    low, high, descriptions = SAMPLE_DATA["Rent"]
    cursor = date(start.year, start.month, 1)
    while cursor <= today:
        db.add_expense(cursor, "Rent", 10000, descriptions[0])
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)

    # A few sample budgets for the budget-status feature.
    for category, limit in {"Food": 6000, "Transport": 2500, "Shopping": 4000,
                            "Entertainment": 2000}.items():
        db.set_budget(category, limit)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the expense database with sample data.")
    parser.add_argument("--count", type=int, default=150, help="number of random expenses")
    parser.add_argument("--reset", action="store_true", help="delete existing expenses first")
    parser.add_argument("--seed", type=int, default=None, help="random seed for repeatable data")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    with ExpenseDatabase() as db:
        if args.reset:
            removed = db.clear_all_expenses()
            print(f"Removed {removed} existing expenses.")
        seed(db, args.count)
        print(f"Done. The database now has {db.count_expenses()} expenses.")
        print(f"Total spent: {db.get_total_spent():,.2f}")


if __name__ == "__main__":
    main()
