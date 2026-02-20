import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime

@dataclass
class Ingredient:
    """Ингредиент (алкогольный напиток)"""
    id: Optional[int]
    name: str
    alcohol_percent: float
    volume_ml: float
    quantity: int
    price_per_unit: float

    @property
    def total_volume(self) -> float:
        return self.volume_ml * self.quantity

@dataclass
class Cocktail:
    """Коктейль"""
    id: Optional[int]
    name: str
    price: float

@dataclass
class Sale:
    """Продажа"""
    id: Optional[int]
    item_type: str
    item_id: int
    quantity: float
    total_price: float
    date: str

class DrinkDatabase:
    def __init__(self, db_name: str = "drinks.db"):
        self.conn = sqlite3.connect(db_name)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                alcohol_percent REAL NOT NULL,
                volume_ml REAL NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                price_per_unit REAL NOT NULL
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS cocktails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                price REAL NOT NULL
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                cocktail_id INTEGER,
                ingredient_id INTEGER,
                volume_ml REAL NOT NULL,
                FOREIGN KEY (cocktail_id) REFERENCES cocktails (id) ON DELETE CASCADE,
                FOREIGN KEY (ingredient_id) REFERENCES ingredients (id) ON DELETE CASCADE,
                PRIMARY KEY (cocktail_id, ingredient_id)
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_type TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                quantity REAL NOT NULL,
                total_price REAL NOT NULL,
                date TEXT NOT NULL
            )
        """)

        self.conn.commit()

    def add_ingredient(self, ingredient: Ingredient) -> int:
        try:
            self.cursor.execute("""
                INSERT INTO ingredients (name, alcohol_percent, volume_ml, quantity, price_per_unit)
                VALUES (?, ?, ?, ?, ?)
            """, (ingredient.name, ingredient.alcohol_percent, ingredient.volume_ml,
                  ingredient.quantity, ingredient.price_per_unit))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"Ингредиент '{ingredient.name}' уже существует")

    def get_all_ingredients(self) -> List[Ingredient]:
        self.cursor.execute("SELECT * FROM ingredients ORDER BY name")
        return [Ingredient(
            id=row['id'],
            name=row['name'],
            alcohol_percent=row['alcohol_percent'],
            volume_ml=row['volume_ml'],
            quantity=row['quantity'],
            price_per_unit=row['price_per_unit']
        ) for row in self.cursor.fetchall()]

    def get_ingredient_by_id(self, ing_id: int) -> Optional[Ingredient]:
        self.cursor.execute("SELECT * FROM ingredients WHERE id=?", (ing_id,))
        row = self.cursor.fetchone()
        if row:
            return Ingredient(
                id=row['id'], name=row['name'], alcohol_percent=row['alcohol_percent'],
                volume_ml=row['volume_ml'], quantity=row['quantity'], price_per_unit=row['price_per_unit']
            )
        return None

    def update_ingredient_quantity(self, ing_id: int, delta: int) -> bool:
        self.cursor.execute("UPDATE ingredients SET quantity = quantity + ? WHERE id=?", (delta, ing_id))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def add_cocktail(self, name: str, price: float, recipe: Dict[int, float]) -> int:
        try:
            self.cursor.execute("INSERT INTO cocktails (name, price) VALUES (?, ?)", (name, price))
            cocktail_id = self.cursor.lastrowid

            for ing_id, volume in recipe.items():
                self.cursor.execute("""
                    INSERT INTO recipes (cocktail_id, ingredient_id, volume_ml)
                    VALUES (?, ?, ?)
                """, (cocktail_id, ing_id, volume))

            self.conn.commit()
            return cocktail_id
        except sqlite3.IntegrityError:
            raise ValueError(f"Коктейль '{name}' уже существует")

    def get_all_cocktails(self) -> List[Dict]:
        self.cursor.execute("SELECT * FROM cocktails ORDER BY name")
        cocktails = []
        for row in self.cursor.fetchall():
            self.cursor.execute("""
                SELECT r.volume_ml, i.alcohol_percent, i.name
                FROM recipes r
                JOIN ingredients i ON r.ingredient_id = i.id
                WHERE r.cocktail_id = ?
            """, (row['id'],))
            recipe = self.cursor.fetchall()

            total_alcohol = 0
            total_volume = 0
            recipe_dict = {}
            for r in recipe:
                vol = r['volume_ml']
                alcohol = r['alcohol_percent']
                total_alcohol += vol * alcohol / 100
                total_volume += vol
                recipe_dict[r['name']] = vol

            alcohol_percent = (total_alcohol / total_volume * 100) if total_volume > 0 else 0

            cocktails.append({
                'id': row['id'],
                'name': row['name'],
                'price': row['price'],
                'alcohol_percent': round(alcohol_percent, 1),
                'recipe': recipe_dict,
                'volume': total_volume
            })
        return cocktails

    def get_cocktail_by_id(self, cocktail_id: int) -> Optional[Dict]:
        self.cursor.execute("SELECT * FROM cocktails WHERE id=?", (cocktail_id,))
        row = self.cursor.fetchone()
        if not row:
            return None

        self.cursor.execute("""
            SELECT r.volume_ml, i.id, i.name, i.alcohol_percent
            FROM recipes r
            JOIN ingredients i ON r.ingredient_id = i.id
            WHERE r.cocktail_id = ?
        """, (cocktail_id,))
        recipe_rows = self.cursor.fetchall()

        recipe = {}
        total_alcohol = 0
        total_volume = 0

        for r in recipe_rows:
            recipe[r['id']] = r['volume_ml']
            total_alcohol += r['volume_ml'] * r['alcohol_percent'] / 100
            total_volume += r['volume_ml']

        alcohol_percent = (total_alcohol / total_volume * 100) if total_volume > 0 else 0

        return {
            'id': row['id'],
            'name': row['name'],
            'price': row['price'],
            'recipe': recipe,
            'alcohol_percent': round(alcohol_percent, 1),
            'volume': total_volume
        }

    def check_cocktail_availability(self, cocktail_id: int) -> tuple[bool, str]:
        cocktail = self.get_cocktail_by_id(cocktail_id)
        if not cocktail:
            return False, "Коктейль не найден"

        for ing_id, need_vol in cocktail['recipe'].items():
            ing = self.get_ingredient_by_id(ing_id)
            if not ing:
                return False, f"Ингредиент ID {ing_id} не найден"

            if ing.quantity <= 0:
                return False, f"Нет {ing.name} на складе"

            available_vol = ing.quantity * ing.volume_ml
            if available_vol < need_vol:
                return False, f"Недостаточно {ing.name}. Нужно {need_vol}мл, есть {available_vol}мл"

        return True, "Доступен"

    def sell_cocktail(self, cocktail_id: int) -> bool:
        cocktail = self.get_cocktail_by_id(cocktail_id)
        if not cocktail:
            messagebox.showerror("Ошибка", "Коктейль не найден")
            return False

        available, msg = self.check_cocktail_availability(cocktail_id)
        if not available:
            messagebox.showerror("Ошибка", msg)
            return False

        for ing_id, need_vol in cocktail['recipe'].items():
            ing = self.get_ingredient_by_id(ing_id)
            units_needed = (need_vol + ing.volume_ml - 1) // ing.volume_ml
            self.update_ingredient_quantity(ing_id, -units_needed)

        self.cursor.execute("""
            INSERT INTO sales (item_type, item_id, quantity, total_price, date)
            VALUES (?, ?, ?, ?, ?)
        """, ('cocktail', cocktail_id, 1, cocktail['price'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
        return True

    def sell_ingredient(self, ing_id: int, quantity: int) -> bool:
        ing = self.get_ingredient_by_id(ing_id)
        if not ing:
            messagebox.showerror("Ошибка", "Ингредиент не найден")
            return False

        if ing.quantity < quantity:
            messagebox.showerror("Ошибка", f"Недостаточно {ing.name}. Есть {ing.quantity}, запрошено {quantity}")
            return False

        total_price = quantity * ing.price_per_unit
        self.update_ingredient_quantity(ing_id, -quantity)

        self.cursor.execute("""
            INSERT INTO sales (item_type, item_id, quantity, total_price, date)
            VALUES (?, ?, ?, ?, ?)
        """, ('ingredient', ing_id, quantity, total_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
        return True

    def restock_ingredient(self, ing_id: int, quantity: int) -> bool:
        ing = self.get_ingredient_by_id(ing_id)
        if not ing:
            messagebox.showerror("Ошибка", "Ингредиент не найден")
            return False

        self.update_ingredient_quantity(ing_id, quantity)
        messagebox.showinfo("Успех", f"Добавлено {quantity} ед. {ing.name}")
        return True

    def get_sales_report(self) -> List[Dict]:
        self.cursor.execute("SELECT * FROM sales ORDER BY date DESC LIMIT 100")
        return [dict(row) for row in self.cursor.fetchall()]

    def close(self):
        self.conn.close()

class DrinkApp:
    def __init__(self, root):
        self.root = root
        self.root.title(" I love drink - Учет напитков и коктейлей")
        self.root.geometry("1000x700")
        self.db = DrinkDatabase()

        self.status_var = tk.StringVar()
        self.status_var.set("Готов к работе")
        status_bar = tk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.create_ingredients_tab()
        self.create_cocktails_tab()
        self.create_sales_tab()
        self.create_reports_tab()

    def create_ingredients_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=" Ингредиенты")

        toolbar = tk.Frame(tab, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=5)

        tk.Button(toolbar, text=" Добавить ингредиент", command=self.add_ingredient_dialog,
                  bg="#27ae60", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text=" Пополнить запас", command=self.restock_dialog,
                  bg="#2980b9", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text=" Обновить", command=self.refresh_ingredients,
                  bg="#7f8c8d", fg="white").pack(side=tk.LEFT, padx=2)

        columns = ("id", "Название", "Крепость", "Объем ед.", "Кол-во", "Цена за ед.", "Общий объем", "Общая стоимость")
        self.ing_tree = ttk.Treeview(tab, columns=columns, show="headings", height=15)

        for col in columns:
            self.ing_tree.heading(col, text=col)
            width = 50 if col == "id" else 100
            self.ing_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.ing_tree.yview)
        self.ing_tree.configure(yscrollcommand=scrollbar.set)

        self.ing_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.refresh_ingredients()

    def create_cocktails_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=" Коктейли")

        toolbar = tk.Frame(tab, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=5)

        tk.Button(toolbar, text=" Добавить коктейль", command=self.add_cocktail_dialog,
                  bg="#27ae60", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text=" Продать", command=self.sell_cocktail_dialog,
                  bg="#e67e22", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text=" Обновить", command=self.refresh_cocktails,
                  bg="#7f8c8d", fg="white").pack(side=tk.LEFT, padx=2)

        columns = ("id", "Название", "Крепость", "Объем", "Цена", "Состав", "Доступность")
        self.cock_tree = ttk.Treeview(tab, columns=columns, show="headings", height=15)

        for col in columns:
            self.cock_tree.heading(col, text=col)
            width = 50 if col == "id" else 120
            self.cock_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.cock_tree.yview)
        self.cock_tree.configure(yscrollcommand=scrollbar.set)

        self.cock_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.refresh_cocktails()

    def create_sales_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=" Продажи")

        toolbar = tk.Frame(tab, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=5)

        tk.Button(toolbar, text=" Продать коктейль", command=self.sell_cocktail_dialog,
                  bg="#e67e22", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text=" Продать ингредиент", command=self.sell_ingredient_dialog,
                  bg="#e67e22", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text=" Пополнить", command=self.restock_dialog,
                  bg="#2980b9", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text=" Обновить", command=self.refresh_sales,
                  bg="#7f8c8d", fg="white").pack(side=tk.LEFT, padx=2)

        columns = ("id", "Тип", "Название", "Кол-во", "Сумма", "Дата")
        self.sales_tree = ttk.Treeview(tab, columns=columns, show="headings", height=15)

        for col in columns:
            self.sales_tree.heading(col, text=col)
            self.sales_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.sales_tree.yview)
        self.sales_tree.configure(yscrollcommand=scrollbar.set)

        self.sales_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.refresh_sales()

    def create_reports_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=" Отчеты")

        btn_frame = tk.Frame(tab)
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text=" Отчет по продажам", command=self.show_sales_report,
                  bg="#8e44ad", fg="white", font=("Arial", 12), width=20).pack(pady=5)

        tk.Button(btn_frame, text=" Остатки на складе", command=self.show_stock_report,
                  bg="#8e44ad", fg="white", font=("Arial", 12), width=20).pack(pady=5)

        self.report_text = tk.Text(tab, height=20, width=80, font=("Courier", 10))
        self.report_text.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

    def refresh_ingredients(self):
        for row in self.ing_tree.get_children():
            self.ing_tree.delete(row)

        total_value = 0
        for ing in self.db.get_all_ingredients():
            total_stock_value = ing.quantity * ing.price_per_unit
            total_value += total_stock_value
            self.ing_tree.insert("", tk.END, values=(
                ing.id, ing.name, f"{ing.alcohol_percent}%", f"{ing.volume_ml}мл",
                ing.quantity, f"{ing.price_per_unit} руб.", f"{ing.total_volume}мл",
                f"{total_stock_value} руб."
            ))

        self.status_var.set(f"Всего ингредиентов: {len(self.db.get_all_ingredients())}, Общая стоимость: {total_value} руб.")

    def add_ingredient_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Добавить ингредиент")
        dialog.geometry("350x300")
        dialog.transient(self.root)
        dialog.grab_set()

        fields = {}
        labels = ["Название:", "Крепость (%):", "Объем единицы (мл):", "Количество:", "Цена за ед. (руб.):"]

        for i, label in enumerate(labels):
            tk.Label(dialog, text=label).grid(row=i, column=0, padx=10, pady=5, sticky=tk.W)
            entry = tk.Entry(dialog, width=25)
            entry.grid(row=i, column=1, padx=10, pady=5)
            fields[label] = entry

        def save():
            try:
                name = fields["Название:"].get().strip()
                alcohol = float(fields["Крепость (%):"].get())
                volume = float(fields["Объем единицы (мл):"].get())
                quantity = int(fields["Количество:"].get())
                price = float(fields["Цена за ед. (руб.):"].get())

                if not name:
                    messagebox.showerror("Ошибка", "Введите название")
                    return

                ing = Ingredient(None, name, alcohol, volume, quantity, price)
                self.db.add_ingredient(ing)
                self.refresh_ingredients()
                dialog.destroy()
                messagebox.showinfo("Успех", "Ингредиент добавлен")
            except ValueError:
                messagebox.showerror("Ошибка", "Проверьте правильность ввода чисел")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

        tk.Button(dialog, text="Сохранить", command=save, bg="#27ae60", fg="white").grid(row=5, column=0, columnspan=2, pady=20)

    def restock_dialog(self):
        ingredients = self.db.get_all_ingredients()
        if not ingredients:
            messagebox.showwarning("Предупреждение", "Нет ингредиентов")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Пополнить запас")
        dialog.geometry("350x200")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Ингредиент:").grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        ing_var = tk.StringVar()
        ing_combo = ttk.Combobox(dialog, textvariable=ing_var, values=[f"{i.id}: {i.name}" for i in ingredients])
        ing_combo.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(dialog, text="Количество:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        qty_entry = tk.Entry(dialog, width=10)
        qty_entry.grid(row=1, column=1, padx=10, pady=5)

        def restock():
            try:
                ing_id = int(ing_combo.get().split(":")[0])
                quantity = int(qty_entry.get())
                if quantity <= 0:
                    messagebox.showerror("Ошибка", "Количество должно быть положительным")
                    return
                self.db.restock_ingredient(ing_id, quantity)
                self.refresh_ingredients()
                dialog.destroy()
            except:
                messagebox.showerror("Ошибка", "Проверьте ввод")

        tk.Button(dialog, text="Пополнить", command=restock, bg="#2980b9", fg="white").grid(row=2, column=0, columnspan=2, pady=20)

    def refresh_cocktails(self):
        for row in self.cock_tree.get_children():
            self.cock_tree.delete(row)

        for c in self.db.get_all_cocktails():
            available, msg = self.db.check_cocktail_availability(c['id'])
            recipe_str = ", ".join([f"{name}: {vol}мл" for name, vol in c['recipe'].items()])

            self.cock_tree.insert("", tk.END, values=(
                c['id'], c['name'], f"{c['alcohol_percent']}%", f"{c['volume']}мл",
                f"{c['price']} руб.", recipe_str[:50] + "..." if len(recipe_str) > 50 else recipe_str,
                "✅" if available else "❌"
            ))

    def add_cocktail_dialog(self):
        ingredients = self.db.get_all_ingredients()
        if not ingredients:
            messagebox.showwarning("Предупреждение", "Сначала добавьте ингредиенты")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Добавить коктейль")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Название:").grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        name_entry = tk.Entry(dialog, width=30)
        name_entry.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(dialog, text="Цена (руб.):").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        price_entry = tk.Entry(dialog, width=30)
        price_entry.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(dialog, text="Рецепт:", font=("Arial", 10, "bold")).grid(row=2, column=0, columnspan=2, pady=10)

        recipe_vars = {}
        for i, ing in enumerate(ingredients, start=3):
            tk.Label(dialog, text=f"{ing.name} ({ing.volume_ml}мл):").grid(row=i, column=0, padx=10, pady=2, sticky=tk.W)
            entry = tk.Entry(dialog, width=10)
            entry.grid(row=i, column=1, padx=10, pady=2, sticky=tk.W)
            recipe_vars[ing.id] = entry

        def save():
            try:
                name = name_entry.get().strip()
                price = float(price_entry.get())

                recipe = {}
                for ing_id, entry in recipe_vars.items():
                    vol = entry.get().strip()
                    if vol:
                        recipe[ing_id] = float(vol)

                if not name or not recipe:
                    messagebox.showerror("Ошибка", "Заполните название и рецепт")
                    return

                self.db.add_cocktail(name, price, recipe)
                self.refresh_cocktails()
                dialog.destroy()
                messagebox.showinfo("Успех", "Коктейль добавлен")
            except ValueError:
                messagebox.showerror("Ошибка", "Проверьте ввод чисел")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

        tk.Button(dialog, text="Сохранить", command=save, bg="#27ae60", fg="white").grid(row=len(ingredients)+3, column=0, columnspan=2, pady=20)

    def sell_cocktail_dialog(self):
        cocktails = self.db.get_all_cocktails()
        if not cocktails:
            messagebox.showwarning("Предупреждение", "Нет коктейлей")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Продажа коктейля")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Коктейль:").pack(pady=10)
        cocktail_var = tk.StringVar()
        cocktail_combo = ttk.Combobox(dialog, textvariable=cocktail_var, values=[f"{c['id']}: {c['name']} ({c['price']} руб.)" for c in cocktails])
        cocktail_combo.pack(pady=5)

        def sell():
            try:
                cocktail_id = int(cocktail_combo.get().split(":")[0])
                if self.db.sell_cocktail(cocktail_id):
                    self.refresh_ingredients()
                    self.refresh_cocktails()
                    self.refresh_sales()
                    messagebox.showinfo("Успех", "Продажа выполнена")
                dialog.destroy()
            except:
                messagebox.showerror("Ошибка", "Выберите коктейль")

        tk.Button(dialog, text="Продать", command=sell, bg="#e67e22", fg="white").pack(pady=20)

    def sell_ingredient_dialog(self):
        ingredients = self.db.get_all_ingredients()
        if not ingredients:
            messagebox.showwarning("Предупреждение", "Нет ингредиентов")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Продажа ингредиента")
        dialog.geometry("400x250")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Ингредиент:").pack(pady=10)
        ing_var = tk.StringVar()
        ing_combo = ttk.Combobox(dialog, textvariable=ing_var, values=[f"{i.id}: {i.name} ({i.price_per_unit} руб./ед.)" for i in ingredients])
        ing_combo.pack(pady=5)

        tk.Label(dialog, text="Количество:").pack(pady=10)
        qty_entry = tk.Entry(dialog, width=10)
        qty_entry.pack(pady=5)

        def sell():
            try:
                ing_id = int(ing_combo.get().split(":")[0])
                quantity = int(qty_entry.get())
                if quantity <= 0:
                    messagebox.showerror("Ошибка", "Количество должно быть положительным")
                    return
                if self.db.sell_ingredient(ing_id, quantity):
                    self.refresh_ingredients()
                    self.refresh_sales()
                    messagebox.showinfo("Успех", "Продажа выполнена")
                dialog.destroy()
            except:
                messagebox.showerror("Ошибка", "Проверьте ввод")

        tk.Button(dialog, text="Продать", command=sell, bg="#e67e22", fg="white").pack(pady=20)

    def refresh_sales(self):
        for row in self.sales_tree.get_children():
            self.sales_tree.delete(row)

        sales = self.db.get_sales_report()
        for sale in sales:
            if sale['item_type'] == 'cocktail':
                cocktail = self.db.get_cocktail_by_id(sale['item_id'])
                name = cocktail['name'] if cocktail else f"Коктейль ID {sale['item_id']}"
            else:
                ing = self.db.get_ingredient_by_id(sale['item_id'])
                name = ing.name if ing else f"Ингредиент ID {sale['item_id']}"

            self.sales_tree.insert("", tk.END, values=(
                sale['id'],
                " Коктейль" if sale['item_type'] == 'cocktail' else " Ингредиент",
                name,
                sale['quantity'],
                f"{sale['total_price']} руб.",
                sale['date']
            ))

    def show_sales_report(self):
        self.report_text.delete(1.0, tk.END)

        sales = self.db.get_sales_report()
        total = 0

        report = "=" * 70 + "\n"
        report += " " * 25 + "ОТЧЕТ О ПРОДАЖАХ\n"
        report += "=" * 70 + "\n\n"

        for sale in sales:
            report += f"{sale['date']} | "
            if sale['item_type'] == 'cocktail':
                cocktail = self.db.get_cocktail_by_id(sale['item_id'])
                name = cocktail['name'] if cocktail else f"Коктейль ID {sale['item_id']}"
                report += f" {name} | {sale['quantity']} шт. | {sale['total_price']} руб.\n"
            else:
                ing = self.db.get_ingredient_by_id(sale['item_id'])
                name = ing.name if ing else f"Ингредиент ID {sale['item_id']}"
                report += f" {name} | {sale['quantity']} ед. | {sale['total_price']} руб.\n"
            total += sale['total_price']

        report += "\n" + "=" * 70 + "\n"
        report += f"ИТОГО: {total} руб.\n"
        report += "=" * 70 + "\n"

        self.report_text.insert(1.0, report)

    def show_stock_report(self):
        self.report_text.delete(1.0, tk.END)

        ingredients = self.db.get_all_ingredients()
        cocktails = self.db.get_all_cocktails()

        report = "=" * 70 + "\n"
        report += " " * 25 + "ОСТАТКИ НА СКЛАДЕ\n"
        report += "=" * 70 + "\n\n"

        report += " ИНГРЕДИЕНТЫ:\n"
        report += "-" * 50 + "\n"
        for ing in ingredients:
            report += f"{ing.name}: {ing.quantity} ед. ({ing.total_volume}мл) - {ing.quantity * ing.price_per_unit} руб.\n"

        report += "\n КОКТЕЙЛИ (доступность):\n"
        report += "-" * 50 + "\n"
        for c in cocktails:
            available, _ = self.db.check_cocktail_availability(c['id'])
            status = "✅" if available else "❌"
            report += f"{status} {c['name']}: {c['price']} руб., {c['alcohol_percent']}%\n"

        self.report_text.insert(1.0, report)

def main():
    root = tk.Tk()
    app = DrinkApp(root)
    root.mainloop()

if __name__ == "__main__":

    main()
