"""
analysis.py - Data Processing and Visualization Module (Member C)

Takes data from database.py and returns Matplotlib figures 
ready to be embedded into Member A's Tkinter GUI.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from database import ExpenseDatabase


def generate_category_pie_chart(db: ExpenseDatabase) -> plt.Figure:
    """Generate a pie chart showing total expenses per category."""
    # 1. Fetch pre-aggregated category totals from Member B's API
    totals = db.get_category_totals()
    
    fig, ax = plt.subplots(figsize=(6, 6))
    
    # Handle empty database state
    if not totals:
        ax.text(0.5, 0.5, "No Expense Data Available", ha="center", va="center", fontsize=12)
        ax.axis("off")
        return fig

    # 2. Extract categories and total values
    categories = [t["category"] for t in totals]
    amounts = [t["total"] for t in totals]

    # 3. Apply color palette and styling
    colors = plt.cm.Set3(range(len(categories)))
    ax.pie(
        amounts,
        labels=categories,
        autopct="%1.1f%%",
        startangle=90,
        colors=colors,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    ax.set_title("Expenses by Category", fontsize=14, pad=15)
    ax.axis("equal")
    return fig


def generate_daily_bar_chart(db: ExpenseDatabase) -> plt.Figure:
    """Generate a bar chart showing spending trends over time."""
    # 1. Fetch data as a Pandas DataFrame using Member B's built-in helper
    df = db.get_expenses_df()
    
    fig, ax = plt.subplots(figsize=(8, 4.5))
    
    # Handle empty database state
    if df.empty:
        ax.text(0.5, 0.5, "No Expense Data Available", ha="center", va="center", fontsize=12)
        ax.axis("off")
        return fig

    # 2. Aggregate total spent per date
    daily_totals = (
        df.groupby("date")["amount"]
        .sum()
        .reset_index()
        .sort_values("date")
    )

    # Convert dates to string format YYYY-MM-DD for clear labeling
    date_labels = daily_totals["date"].dt.strftime("%Y-%m-%d")

    # 3. Create Bar Chart
    bars = ax.bar(date_labels, daily_totals["amount"], color="#5b9bd5", width=0.6)
    
    # Add currency labels on top of bars
    ax.bar_label(bars, fmt="₹%.0f", padding=3, fontsize=9)
    
    ax.set_title("Daily Spending Trends", fontsize=14, pad=15)
    ax.set_xlabel("Date", fontsize=10)
    ax.set_ylabel("Total Spent", fontsize=10)
    
    # Format Y-axis with Indian Rupee symbol
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("₹{x:,.0f}"))
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


# --- TEST BLOCK ---
if __name__ == "__main__":
    # Test your charts using a temporary in-memory database filled via seed_data
    from seed_data import seed
    
    print("Testing analysis.py with seeded test database...")
    test_db = ExpenseDatabase(":memory:")
    seed(test_db, count=50) # Seed 50 sample expenses
    
    # Generate charts
    fig1 = generate_category_pie_chart(test_db)
    fig2 = generate_daily_bar_chart(test_db)
    
    # Show pop-up windows for local testing
    plt.show()
    test_db.close()
