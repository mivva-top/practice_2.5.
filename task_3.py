import sqlite3
import urllib.request
import json


class DatabaseManager:

    def __init__(self, db_name="currency.db"):
        self.db_name = db_name
        self._create_tables()

    def _get_connection(self):
        return sqlite3.connect(self.db_name)

    def _create_tables(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS groups
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           name
                           TEXT
                           UNIQUE
                           NOT
                           NULL
                       )
                       ''')

        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS group_items
                       (
                           group_id
                           INTEGER,
                           currency_code
                           TEXT,
                           FOREIGN
                           KEY
                       (
                           group_id
                       ) REFERENCES groups
                       (
                           id
                       )
                           )
                       ''')

        conn.commit()
        conn.close()


    def add_group(self, name):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO groups (name) VALUES (?)', (name,))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()

    def get_groups(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM groups ORDER BY name')
        groups = [row[0] for row in cursor.fetchall()]
        conn.close()
        return groups

    def delete_group(self, name):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM groups WHERE name = ?', (name,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False

        group_id = result[0]

        cursor.execute('DELETE FROM group_items WHERE group_id = ?', (group_id,))
        cursor.execute('DELETE FROM groups WHERE id = ?', (group_id,))

        conn.commit()
        conn.close()
        return True

    def add_currency(self, group_name, currency):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM groups WHERE name = ?', (group_name,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False

        group_id = result[0]

        cursor.execute('INSERT INTO group_items (group_id, currency_code) VALUES (?, ?)',
                       (group_id, currency.upper()))
        conn.commit()
        conn.close()
        return True

    def remove_currency(self, group_name, currency):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM groups WHERE name = ?', (group_name,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False

        group_id = result[0]

        cursor.execute('DELETE FROM group_items WHERE group_id = ? AND currency_code = ?',
                       (group_id, currency.upper()))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    def get_group_currencies(self, group_name):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM groups WHERE name = ?', (group_name,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return []

        group_id = result[0]

        cursor.execute('SELECT currency_code FROM group_items WHERE group_id = ? ORDER BY currency_code',
                       (group_id,))
        currencies = [row[0] for row in cursor.fetchall()]
        conn.close()
        return currencies


class SimpleCurrencyApp:

    def __init__(self):
        self.url = "https://www.cbr-xml-daily.ru/daily_json.js"
        self.data = None
        self.db = DatabaseManager()

    def load_data(self):
        try:
            with urllib.request.urlopen(self.url) as response:
                self.data = json.loads(response.read().decode('utf-8'))
                return True
        except:
            print("Ошибка загрузки. Проверьте интернет.")
            return False

    def show_all(self):
        if not self.data and not self.load_data():
            return

        print("\n" + "=" * 60)
        print("ВСЕ ВАЛЮТЫ")
        print("=" * 60)
        print(f"{'Код':<6} {'Название':<35} {'Курс':<10}")
        print("-" * 60)

        print(f"{'RUB':<6} {'Российский рубль':<35} {'1.0000':<10}")

        for code, info in sorted(self.data['Valute'].items()):
            name = info.get('Name', '')[:35]
            value = info.get('Value', 0)
            print(f"{code:<6} {name:<35} {value:<10.4f}")

    def show_one(self, code):
        if not self.data and not self.load_data():
            return

        code = code.upper()

        if code == "RUB":
            print(f"\n{RUB} - Российский рубль: 1.0000")
            return

        if code not in self.data['Valute']:
            print(f"Валюта {code} не найдена")
            return

        curr = self.data['Valute'][code]
        print(f"\n{code} - {curr['Name']}")
        print(f"Курс: {curr['Value']:.4f}")
        print(f"Номинал: {curr['Nominal']}")

        change = curr['Value'] - curr['Previous']
        if change > 0:
            print(f"Изменение: +{change:.4f} ↑")
        elif change < 0:
            print(f"Изменение: {change:.4f} ↓")

    def run(self):
        print("=" * 50)
        print("МОНИТОРИНГ ВАЛЮТ")
        print("=" * 50)

        self.load_data()

        while True:
            print("\nМЕНЮ:")
            print("1. Все валюты")
            print("2. Найти валюту")
            print("3. Создать группу")
            print("4. Мои группы")
            print("5. Добавить в группу")
            print("6. Удалить из группы")
            print("7. Показать группу")
            print("8. Удалить группу")
            print("0. Выход")

            choice = input("\nВыберите: ").strip()

            if choice == "0":
                print("До свидания!")
                break

            elif choice == "1":
                self.show_all()

            elif choice == "2":
                code = input("Код валюты (USD, EUR...): ").strip().upper()
                self.show_one(code)

            elif choice == "3":
                name = input("Название группы: ").strip()
                if self.db.add_group(name):
                    print(f"Группа '{name}' создана")
                else:
                    print("Такая группа уже есть")

            elif choice == "4":
                groups = self.db.get_groups()
                if groups:
                    print("\nВаши группы:")
                    for g in groups:
                        print(f"  • {g}")
                else:
                    print("Нет групп")

            elif choice == "5":
                group = input("Группа: ").strip()
                code = input("Код валюты: ").strip().upper()
                if self.db.add_currency(group, code):
                    print(f"{code} добавлен в {group}")
                else:
                    print("Ошибка")

            elif choice == "6":
                group = input("Группа: ").strip()
                code = input("Код валюты: ").strip().upper()
                if self.db.remove_currency(group, code):
                    print(f"{code} удален из {group}")
                else:
                    print("Не найдено")

            elif choice == "7":
                group = input("Группа: ").strip()
                currencies = self.db.get_group_currencies(group)
                if currencies:
                    print(f"\n{group}:")
                    for code in currencies:
                        if self.data and code in self.data.get('Valute', {}):
                            rate = self.data['Valute'][code]['Value']
                            print(f"  {code}: {rate:.4f}")
                        else:
                            print(f"  {code}")
                else:
                    print("Группа пуста или не существует")

            elif choice == "8":
                group = input("Группа для удаления: ").strip()
                confirm = input(f"Удалить '{group}'? (да/нет): ").lower()
                if confirm in ['да', 'yes', 'y', 'д']:
                    if self.db.delete_group(group):
                        print("Группа удалена")
                    else:
                        print("Группа не найдена")

            input("\nНажмите Enter...")


def main():
    app = SimpleCurrencyApp()
    app.run()


if __name__ == "__main__":
    main()