import sqlite3
import config as cnfg
from datetime import datetime

class DBManager(object):

    def __init__(self):
        self.db_name = cnfg.DB_NAME
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS groups (
                                group_id VARCHAR(50) PRIMARY KEY,
                                year INT
                            );                
                            ''')

        self.cursor.execute('''CREATE TABLE IF NOT EXISTS teachers (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                full_name VARCHAR(255),
                                department VARCHAR(255)
                            );                
                            ''')

        self.cursor.execute('''CREATE TABLE IF NOT EXISTS time_tables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id VARCHAR(50),
                    teacher_id INTEGER,
                    week_num INTEGER,
                    couple_num INTEGER,
                    day_of_week VARCHAR(20),
                    auditorium VARCHAR(100),
                    course_name VARCHAR(255)
                );
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INT PRIMARY KEY
            );
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS last_xlsx_update (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                last_update DATETIME NOT NULL
            );
        ''')
        self.conn.commit()

    def add_new_user(self, user_id):
        self.cursor.execute("INSERT OR REPLACE INTO users (user_id) VALUES (?)", (user_id,))
        self.conn.commit()

    def create_or_update_time_table(self, groups, teachers, time_table_info):
        self.cursor.execute("DELETE FROM groups")
        self.cursor.execute("DELETE FROM teachers")
        self.cursor.execute("DELETE FROM time_tables")

        group_tuples = [(g["group_id"], g["year"]) for g in groups]
        self.cursor.executemany("INSERT INTO groups (group_id, year) VALUES (?, ?)", group_tuples)

        teacher_tuples = [(t["full_name"], t["department"]) for t in teachers]
        self.cursor.executemany("INSERT INTO teachers (full_name, department) VALUES (?, ?)", teacher_tuples)

        # Получаем отображение full_name → id
        self.cursor.execute("SELECT id, full_name FROM teachers")
        teacher_map = {name: tid for tid, name in self.cursor.fetchall()}

        time_table_tuples = []
        for tt in time_table_info:
            teacher_id = teacher_map.get(tt["teacher_full_name"])
            if teacher_id is not None:
                time_table_tuples.append((
                    tt["group_id"],
                    teacher_id,
                    tt["week_num"],
                    tt["couple_num"],
                    tt["day_of_week"],
                    tt["auditorium"],
                    tt["course_name"]
                ))

        self.cursor.executemany('''
            INSERT INTO time_tables (
                group_id, teacher_id, week_num, couple_num, day_of_week, auditorium, course_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', time_table_tuples)

        self.conn.commit()

    def get_schedule_by_group(self, group_id):
        self.cursor.execute('''
            SELECT 
                tt.week_num,
                tt.couple_num,
                tt.day_of_week,              -- <-- добавили здесь
                tt.auditorium,
                tt.course_name,
                tt.group_id,
                t.full_name
            FROM time_tables tt
            JOIN teachers t ON tt.teacher_id = t.id
            WHERE tt.group_id = ?
            ORDER BY tt.day_of_week, tt.couple_num, tt.week_num   -- можно сортировать по дню недели тоже
        ''', (group_id,))

        rows = self.cursor.fetchall()
        result = [
            {
                "week_num": row[0],
                "couple_num": row[1],
                "day_of_week": row[2],
                "auditorium": row[3],
                "course_name": row[4],
                "group_id": row[5],
                "teacher_full_name": row[6]
            } for row in rows
        ]
        return result

    def get_schedule_by_teacher(self, teacher_full_name):
        self.cursor.execute('''
            SELECT 
                tt.week_num,
                tt.couple_num,
                tt.day_of_week,            -- <-- добавили
                tt.auditorium,
                tt.course_name,
                tt.group_id,
                t.full_name
            FROM time_tables tt
            JOIN teachers t ON tt.teacher_id = t.id
            WHERE t.full_name = ?
            ORDER BY tt.day_of_week, tt.couple_num, tt.week_num
        ''', (teacher_full_name,))

        rows = self.cursor.fetchall()
        result = [
            {
                "week_num": row[0],
                "couple_num": row[1],
                "day_of_week": row[2],
                "auditorium": row[3],
                "course_name": row[4],
                "group_id": row[5],
                "teacher_full_name": row[6]
            } for row in rows
        ]
        return result

    def get_last_update(self) -> datetime | None:
        self.cursor.execute('SELECT last_update FROM last_xlsx_update ORDER BY last_update DESC LIMIT 1')
        row = self.cursor.fetchone()
        return datetime.fromisoformat(row[0]) if row else None

    def set_last_update(self, new_update: datetime):
        self.cursor.execute('INSERT INTO last_xlsx_update (last_update) VALUES (?)', (new_update.isoformat(),))
        self.conn.commit()

    def get_all_user_ids(self) -> list[int]:
        self.cursor.execute("SELECT DISTINCT user_id FROM users")
        return [row[0] for row in self.cursor.fetchall()]


