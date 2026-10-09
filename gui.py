"""
gui.py - Main User Interface Module (Member A)

Owner: Member A (Frontend / UI / UX)
Tech Stack: Tkinter, ttk, Matplotlib FigureCanvasTkAgg
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Import backend API (Member B) and visualization API (Member C)
from database import ExpenseDatabase, ValidationError, DEFAULT_CATEGORIES
from analysis import generate_category_pie_chart, generate_daily_bar_chart


class ExpenseApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Smart Expense & Budget Analyzer")
        self.root.geometry("1100x680")
        self.root.minsize(900, 600)

        # Initialize Database connection
        self.db = ExpenseDatabase()

        # Handle window closing to safely disconnect DB
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Setup Main Layout (Tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create Tab Frames
        self.tab_expenses = ttk.Frame(self.notebook)
        self.tab_analytics = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_expenses, text=" Expenses & Entry ")
        self.notebook.add(self.tab_analytics, text=" Analytics & Charts ")

        # Build Tab Content
        self.setup_expenses_tab()
        self.setup_analytics_tab()

        # Initial Table Refresh
        self.refresh_table()

    # ------------------------------------------------------------------ #
    # TAB 1: EXPENSES & ENTRY LAYOUT
    # ------------------------------------------------------------------ #
    def setup_expenses_tab(self):
        # Left Frame: Data Entry Form
        form_frame = ttk.LabelFrame(self.tab_expenses, text=" Add New Expense ", padding=15)
        form_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # Date Field
        ttk.Label(form_frame, text="Date (YYYY-MM-DD):").pack(anchor=tk.W, pady=(0, 2))
        self.date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        ttk.Entry(form_frame, textvariable=self.date_var, width=25).pack(anchor=tk.W, pady=(0, 10))

        # Category Dropdown
        ttk.Label(form_frame, text="Category:").pack(anchor=tk.W, pady=(0, 2))
        self.cat_var = tk.StringVar()
        self.cat_combobox = ttk.Combobox(form_frame, textvariable=self.cat_var, values=DEFAULT_CATEGORIES, width=22)
        self.cat_combobox.pack(anchor=tk.W, pady=(0, 10))
        self.cat_combobox.current(0)

        # Amount Field
        ttk.Label(form_frame, text="Amount (₹):").pack(anchor=tk.W, pady=(0, 2))
        self.amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.amount_var, width=25).pack(anchor=tk.W, pady=(0, 10))

        # Description Field
        ttk.Label(form_frame, text="Description:").pack(anchor=tk.W, pady=(0, 2))
        self.desc_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.desc_var, width=25).pack(anchor=tk.W, pady=(0, 15))

        # Action Buttons
        ttk.Button(form_frame, text="➕ Add Expense", command=self.on_add_expense).pack(fill=tk.X, pady=5)
        ttk.Button(form_frame, text="🗑️ Delete Selected", command=self.on_delete_expense).pack(fill=tk.X, pady=5)

        # Right Frame: Expenses Treeview Table
        table_frame = ttk.Frame(self.tab_expenses, padding=10)
        table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        columns = ("id", "date", "category", "amount", "description")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        
        self.tree.heading("id", text="ID")
        self.tree.heading("date", text="Date")
        self.tree.heading("category", text="Category")
        self.tree.heading("amount", text="Amount (₹)")
        self.tree.heading("description", text="Description")

        self.tree.column("id", width=40, anchor=tk.CENTER)
        self.tree.column("date", width=100, anchor=tk.CENTER)
        self.tree.column("category", width=120, anchor=tk.W)
        self.tree.column("amount", width=100, anchor=tk.E)
        self.tree.column("description", width=250, anchor=tk.W)

        # Scrollbar for Table
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # ------------------------------------------------------------------ #
    # TAB 2: ANALYTICS & CHARTS LAYOUT
    # ------------------------------------------------------------------ #
    def setup_analytics_tab(self):
        # Top Control Frame
        top_frame = ttk.Frame(self.tab_analytics, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Button(top_frame, text="🔄 Refresh Charts", command=self.refresh_charts).pack(side=tk.LEFT, padx=5)

        # Charts Display Frame
        self.charts_frame = ttk.Frame(self.tab_analytics, padding=10)
        self.charts_frame.pack(fill=tk.BOTH, expand=True)

        # Container Sub-frames
        self.pie_frame = ttk.Frame(self.charts_frame)
        self.pie_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.bar_frame = ttk.Frame(self.charts_frame)
        self.bar_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------ #
    # EVENT HANDLERS & REFRESH LOGIC
    # ------------------------------------------------------------------ #
    def refresh_table(self):
        """Fetch records from Member B's DB and populate the Treeview table."""
        self.tree.delete(*self.tree.get_children())
        for row in self.db.get_all_expenses():
            self.tree.insert(
                "",
                "end",
                iid=row["id"],  # Use ID as item identifier
                values=(
                    row["id"],
                    row["date"],
                    row["category"],
                    f"{row['amount']:.2f}",
                    row["description"]
                )
            )
        self.refresh_charts()

    def refresh_charts(self):
        """Clear old figures and draw Member C's Matplotlib charts inside Tkinter."""
        # Clear previous canvas widgets
        for widget in self.pie_frame.winfo_children():
            widget.destroy()
        for widget in self.bar_frame.winfo_children():
            widget.destroy()

        # Generate & Embed Pie Chart
        pie_fig = generate_category_pie_chart(self.db)
        pie_canvas = FigureCanvasTkAgg(pie_fig, master=self.pie_frame)
        pie_canvas.draw()
        pie_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Generate & Embed Bar Chart
        bar_fig = generate_daily_bar_chart(self.db)
        bar_canvas = FigureCanvasTkAgg(bar_fig, master=self.bar_frame)
        bar_canvas.draw()
        bar_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def on_add_expense(self):
        """Handle Add Expense button click."""
        try:
            self.db.add_expense(
                date=self.date_var.get(),
                category=self.cat_var.get(),
                amount=self.amount_var.get(),
                description=self.desc_var.get()
            )
            # Clear input fields
            self.amount_var.set("")
            self.desc_var.set("")
            self.refresh_table()
            messagebox.showinfo("Success", "Expense added successfully!")
        except ValidationError as err:
            messagebox.showerror("Validation Error", str(err))

    def on_delete_expense(self):
        """Handle Delete Expense button click (supports multi-selection)."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "Please select at least one expense to delete.")
            return

        ids_to_delete = [int(item_id) for item_id in selected_items]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {len(ids_to_delete)} item(s)?"):
            self.db.delete_many(ids_to_delete)
            self.refresh_table()

    def on_closing(self):
        """Close DB connection safely when user exits app."""
        self.db.close()
        self.root.destroy()


# ------------------------------------------------------------------ #
# ENTRY POINT
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    root = tk.Tk()
    app = ExpenseApp(root)
    root.mainloop()