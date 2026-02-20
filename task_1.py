import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Student:
    first_name: str
    last_name: str
    patronymic: str
    group: str
    grades: List[int]
    id: Optional[int] = None

    def average_grade(self) -> float:
        return sum(self.grades) / len(self.grades) if self.grades else 0.0


class StudentDatabase:
    def __init__(self, db_name: str = "students.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        self.cursor.execute("""
                            CREATE TABLE IF NOT EXISTS students
                            (
                                id
                                INTEGER
                                PRIMARY
                                KEY
                                AUTOINCREMENT,
                                first_name
                                TEXT,
                                last_name
                                TEXT,
                                patronymic
                                TEXT,
                                group_name
                                TEXT,
                                grade1
                                INTEGER,
                                grade2
                                INTEGER,
                                grade3
                                INTEGER,
                                grade4
                                INTEGER
                            )
                            """)
        self.conn.commit()

    def add_student(self, student: Student) -> int:
        self.cursor.execute("""
                            INSERT INTO students (first_name, last_name, patronymic, group_name, grade1, grade2, grade3,
                                                  grade4)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (student.first_name, student.last_name, student.patronymic, student.group,
                                  student.grades[0], student.grades[1], student.grades[2], student.grades[3]))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_all_students(self) -> List[Student]:
        self.cursor.execute("SELECT * FROM students")
        return [Student(id=row[0], first_name=row[1], last_name=row[2],
                        patronymic=row[3], group=row[4], grades=[row[5], row[6], row[7], row[8]])
                for row in self.cursor.fetchall()]

    def get_student_by_id(self, student_id: int) -> Optional[Student]:
        self.cursor.execute("SELECT * FROM students WHERE id=?", (student_id,))
        row = self.cursor.fetchone()
        if row:
            return Student(id=row[0], first_name=row[1], last_name=row[2],
                           patronymic=row[3], group=row[4], grades=[row[5], row[6], row[7], row[8]])
        return None

    def update_student(self, student: Student) -> bool:
        if student.id is None: return False
        self.cursor.execute("""
                            UPDATE students
                            SET first_name=?,
                                last_name=?,
                                patronymic=?,
                                group_name=?,
                                grade1=?,
                                grade2=?,
                                grade3=?,
                                grade4=?
                            WHERE id = ?
                            """, (student.first_name, student.last_name, student.patronymic, student.group,
                                  student.grades[0], student.grades[1], student.grades[2], student.grades[3],
                                  student.id))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def delete_student(self, student_id: int) -> bool:
        self.cursor.execute("DELETE FROM students WHERE id=?", (student_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_groups(self) -> List[str]:
        self.cursor.execute("SELECT DISTINCT group_name FROM students ORDER BY group_name")
        return [row[0] for row in self.cursor.fetchall()]

    def get_students_by_group(self, group_name: str) -> List[Student]:
        self.cursor.execute("SELECT * FROM students WHERE group_name=?", (group_name,))
        return [Student(id=row[0], first_name=row[1], last_name=row[2],
                        patronymic=row[3], group=row[4], grades=[row[5], row[6], row[7], row[8]])
                for row in self.cursor.fetchall()]

    def close(self):
        self.conn.close()


class StudentApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Управление студентами")
        self.root.geometry("900x500")
        self.db = StudentDatabase()
        self.create_widgets()
        self.refresh_table()

    def create_widgets(self):
        toolbar = tk.Frame(self.root, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        buttons = [
            (" Добавить", self.add_student_dialog, "#27ae60"),
            (" Редактировать", self.edit_student_dialog, "#f39c12"),
            (" Удалить", self.delete_student, "#c0392b"),
            (" Обновить", self.refresh_table, "#2980b9"),
            (" Средний балл группы", self.group_average_dialog, "#8e44ad")
        ]

        for text, cmd, color in buttons:
            tk.Button(toolbar, text=text, command=cmd, bg=color, fg="white",
                      font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=2, pady=2)

        search_frame = tk.Frame(self.root)
        search_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        tk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self.filter_table())
        tk.Entry(search_frame, textvariable=self.search_var, width=30).pack(side=tk.LEFT, padx=5)

        self.tree_frame = tk.Frame(self.root)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("id", "Фамилия", "Имя", "Отчество", "Группа", "Оценки", "Средний балл")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings")

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100 if col == "id" else 120)

        scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind('<Double-1>', lambda e: self.view_student_details())

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for s in self.db.get_all_students():
            self.tree.insert("", tk.END, values=(
                s.id, s.last_name, s.first_name, s.patronymic, s.group,
                ", ".join(map(str, s.grades)), f"{s.average_grade():.2f}"
            ))

    def filter_table(self):
        text = self.search_var.get().lower()
        for row in self.tree.get_children():
            self.tree.delete(row)
        for s in self.db.get_all_students():
            if (text in s.last_name.lower() or text in s.first_name.lower() or
                    text in s.patronymic.lower() or text in s.group.lower()):
                self.tree.insert("", tk.END, values=(
                    s.id, s.last_name, s.first_name, s.patronymic, s.group,
                    ", ".join(map(str, s.grades)), f"{s.average_grade():.2f}"
                ))

    def get_selected_id(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Предупреждение", "Выберите студента")
            return None
        return self.tree.item(selected[0])['values'][0]

    def add_student_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Добавить студента")
        dialog.geometry("350x350")
        dialog.transient(self.root)
        dialog.grab_set()

        entries = {}
        fields = ["Фамилия", "Имя", "Отчество", "Группа"]

        for i, field in enumerate(fields):
            tk.Label(dialog, text=field + ":").grid(row=i, column=0, padx=10, pady=5, sticky=tk.W)
            entries[field] = tk.Entry(dialog, width=25)
            entries[field].grid(row=i, column=1, padx=10, pady=5)

        tk.Label(dialog, text="Оценки (4 через запятую):").grid(row=4, column=0, padx=10, pady=5, sticky=tk.W)
        grades_entry = tk.Entry(dialog, width=25)
        grades_entry.grid(row=4, column=1, padx=10, pady=5)

        def save():
            try:
                grades = list(map(int, grades_entry.get().split(',')))
                if len(grades) != 4:
                    messagebox.showerror("Ошибка", "Введите 4 оценки")
                    return
                if not all(1 <= g <= 5 for g in grades):
                    messagebox.showerror("Ошибка", "Оценки от 1 до 5")
                    return

                student = Student(
                    first_name=entries["Имя"].get().strip(),
                    last_name=entries["Фамилия"].get().strip(),
                    patronymic=entries["Отчество"].get().strip(),
                    group=entries["Группа"].get().strip(),
                    grades=grades
                )

                if not all([student.first_name, student.last_name, student.patronymic, student.group]):
                    messagebox.showerror("Ошибка", "Заполните все поля")
                    return

                self.db.add_student(student)
                self.refresh_table()
                dialog.destroy()
                messagebox.showinfo("Успех", "Студент добавлен")
            except ValueError:
                messagebox.showerror("Ошибка", "Оценки должны быть числами")

        tk.Button(dialog, text="Сохранить", command=save, bg="#27ae60", fg="white").grid(row=5, column=0, columnspan=2,
                                                                                         pady=20)

    def edit_student_dialog(self):
        student_id = self.get_selected_id()
        if not student_id: return

        student = self.db.get_student_by_id(student_id)
        if not student: return

        dialog = tk.Toplevel(self.root)
        dialog.title("Редактировать")
        dialog.geometry("350x350")
        dialog.transient(self.root)
        dialog.grab_set()

        fields = {"Фамилия": student.last_name, "Имя": student.first_name,
                  "Отчество": student.patronymic, "Группа": student.group}
        entries = {}

        for i, (field, value) in enumerate(fields.items()):
            tk.Label(dialog, text=field + ":").grid(row=i, column=0, padx=10, pady=5, sticky=tk.W)
            entries[field] = tk.Entry(dialog, width=25)
            entries[field].insert(0, value)
            entries[field].grid(row=i, column=1, padx=10, pady=5)

        tk.Label(dialog, text="Оценки:").grid(row=4, column=0, padx=10, pady=5, sticky=tk.W)
        grades_entry = tk.Entry(dialog, width=25)
        grades_entry.insert(0, ", ".join(map(str, student.grades)))
        grades_entry.grid(row=4, column=1, padx=10, pady=5)

        def update():
            try:
                grades = list(map(int, grades_entry.get().split(',')))
                if len(grades) != 4 or not all(1 <= g <= 5 for g in grades):
                    messagebox.showerror("Ошибка", "Введите 4 оценки от 1 до 5")
                    return

                student.first_name = entries["Имя"].get().strip()
                student.last_name = entries["Фамилия"].get().strip()
                student.patronymic = entries["Отчество"].get().strip()
                student.group = entries["Группа"].get().strip()
                student.grades = grades

                if not all([student.first_name, student.last_name, student.patronymic, student.group]):
                    messagebox.showerror("Ошибка", "Заполните все поля")
                    return

                self.db.update_student(student)
                self.refresh_table()
                dialog.destroy()
                messagebox.showinfo("Успех", "Данные обновлены")
            except ValueError:
                messagebox.showerror("Ошибка", "Оценки должны быть числами")

        tk.Button(dialog, text="Обновить", command=update, bg="#f39c12", fg="white").grid(row=5, column=0, columnspan=2,
                                                                                          pady=20)

    def delete_student(self):
        student_id = self.get_selected_id()
        if not student_id: return

        if messagebox.askyesno("Подтверждение", "Удалить студента?"):
            self.db.delete_student(student_id)
            self.refresh_table()
            messagebox.showinfo("Успех", "Студент удален")

    def view_student_details(self):
        student_id = self.get_selected_id()
        if not student_id: return

        s = self.db.get_student_by_id(student_id)
        if s:
            msg = (f"ID: {s.id}\nФамилия: {s.last_name}\nИмя: {s.first_name}\n"
                   f"Отчество: {s.patronymic}\nГруппа: {s.group}\n"
                   f"Оценки: {', '.join(map(str, s.grades))}\n"
                   f"Средний балл: {s.average_grade():.2f}")
            messagebox.showinfo("Информация о студенте", msg)

    def group_average_dialog(self):
        groups = self.db.get_groups()
        if not groups:
            messagebox.showinfo("Инфо", "Нет групп")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Средний балл группы")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Выберите группу:").pack(pady=10)
        group_var = tk.StringVar()
        combo = ttk.Combobox(dialog, textvariable=group_var, values=groups, state="readonly")
        combo.pack(pady=5)
        if groups: combo.current(0)

        def show():
            group = group_var.get()
            students = self.db.get_students_by_group(group)
            if students:
                avg = sum(s.average_grade() for s in students) / len(students)
                msg = f"Группа: {group}\nКол-во: {len(students)}\nСредний балл: {avg:.2f}"
                messagebox.showinfo("Результат", msg)
            dialog.destroy()

        tk.Button(dialog, text="Показать", command=show, bg="#8e44ad", fg="white").pack(pady=10)

    def __del__(self):
        if hasattr(self, 'db'): self.db.close()


def main():
    root = tk.Tk()
    app = StudentApp(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось запустить программу: {e}")