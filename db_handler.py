import sqlite3
from datetime import date, datetime
import json
import logging
import threading

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path="diary.db"):
        self.db_path = db_path
        self.conn = None
        self.local = threading.local()
        self.connect()

    def get_connection(self):
        """Получает соединение для текущего потока"""
        if not hasattr(self.local, 'conn') or self.local.conn is None:
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.local.conn.row_factory = sqlite3.Row
           
            self.local.conn.execute("PRAGMA foreign_keys = ON")
        return self.local.conn

    def connect(self):
        """Устанавливает соединение с SQLite БД"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            logger.info(f"Подключение к БД {self.db_path} установлено")
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            raise

    def _convert_date(self, date_str):
        """Конвертирует строку даты в объект date"""
        if isinstance(date_str, str):
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        return date_str

    def execute(self, query, args=None, fetch=False, commit=False):
        """Универсальный метод выполнения запросов (потокобезопасный)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if args:
                cursor.execute(query, args)
            else:
                cursor.execute(query)
            
            if fetch:
                result = cursor.fetchall()
                if result:
                    converted_result = []
                    for row in result:
                        row_dict = dict(row)
                        if 'record_date' in row_dict and row_dict['record_date']:
                            row_dict['record_date'] = self._convert_date(row_dict['record_date'])
                        converted_result.append(row_dict)
                    return converted_result
                return result
            else:
                result = None
            
            if commit:
                conn.commit()
            
            return result
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка выполнения запроса: {e}")
            logger.error(f"Запрос: {query}")
            if args:
                logger.error(f"Аргументы: {args}")
            raise e
        finally:
            cursor.close()

    def create_tables(self):
        """Создаёт таблицу (выполняется один раз при старте)"""
        try:
            conn = self.get_connection()
            conn.execute("PRAGMA foreign_keys = ON")
           
            query_create = """
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                record_date DATE NOT NULL,
                mood INTEGER CHECK (mood BETWEEN 1 AND 5),
                work_hours REAL CHECK (work_hours >= 0),
                sleep_hours REAL CHECK (sleep_hours >= 0),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, record_date)
            )
            """
            conn.execute(query_create)
          
            query_index = """
            CREATE INDEX IF NOT EXISTS idx_user_date ON records(user_id, record_date)
            """
            conn.execute(query_index)
            conn.commit()
            
            logger.info("Таблицы успешно созданы")
        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise

    def insert_or_update_record(self, user_id, record_date, mood, work_hours, sleep_hours, comment):
        """Вставляет или обновляет запись за день"""
        try:
            conn = self.get_connection()
          
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM records WHERE user_id = ? AND record_date = ?", (user_id, record_date))
            existing = cursor.fetchone()
            cursor.close()
            
            if existing:
                query = """
                UPDATE records 
                SET mood = ?, work_hours = ?, sleep_hours = ?, comment = ?, created_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND record_date = ?
                """
                cursor = conn.cursor()
                cursor.execute(query, (mood, work_hours, sleep_hours, comment, user_id, record_date))
                conn.commit()
                cursor.close()
                return existing['id']
            else:
                query = """
                INSERT INTO records (user_id, record_date, mood, work_hours, sleep_hours, comment)
                VALUES (?, ?, ?, ?, ?, ?)
                """
                cursor = conn.cursor()
                cursor.execute(query, (user_id, record_date, mood, work_hours, sleep_hours, comment))
                conn.commit()
                last_id = cursor.lastrowid
                cursor.close()
                return last_id
                
        except Exception as e:
            logger.error(f"Ошибка сохранения записи: {e}")
            raise

    def get_record_for_date(self, user_id, record_date):
        """Получает запись за конкретную дату"""
        query = "SELECT * FROM records WHERE user_id = ? AND record_date = ?"
        result = self.execute(query, (user_id, record_date), fetch=True)
        return result[0] if result else None

    def get_records_period(self, user_id, start_date, end_date):
        """Получает все записи пользователя за период"""
        query = """
        SELECT record_date, mood, work_hours, sleep_hours, comment
        FROM records
        WHERE user_id = ? AND record_date BETWEEN ? AND ?
        ORDER BY record_date
        """
        return self.execute(query, (user_id, start_date, end_date), fetch=True)

    def get_last_records(self, user_id, limit=10):
        """Последние N записей"""
        query = """
        SELECT record_date, mood, work_hours, sleep_hours, comment
        FROM records
        WHERE user_id = ?
        ORDER BY record_date DESC
        LIMIT ?
        """
        return self.execute(query, (user_id, limit), fetch=True)

    def delete_all_user_data(self, user_id):
        """Удаляет все данные пользователя"""
        query = "DELETE FROM records WHERE user_id = ?"
        self.execute(query, (user_id,), commit=True)
        logger.info(f"Удалены все данные для пользователя {user_id}")

    def get_stats_for_insights(self, user_id):
        """Возвращает агрегированные данные для инсайтов"""
        query = """
        SELECT
            AVG(mood) as avg_mood,
            AVG(work_hours) as avg_work,
            AVG(sleep_hours) as avg_sleep,
            COUNT(*) as total_days
        FROM records
        WHERE user_id = ?
        """
        overall = self.execute(query, (user_id,), fetch=True)[0]
        
        
        query_sleep = """
        SELECT
            CASE WHEN sleep_hours >= 7 THEN '>=7ч' ELSE '<7ч' END as sleep_category,
            AVG(work_hours) as avg_work,
            AVG(mood) as avg_mood,
            COUNT(*) as days
        FROM records
        WHERE user_id = ?
        GROUP BY sleep_category
        """
        sleep_impact = self.execute(query_sleep, (user_id,), fetch=True)
        
    
        query_work = """
        SELECT
            CASE WHEN work_hours >= 4 THEN '>=4ч' ELSE '<4ч' END as work_category,
            AVG(mood) as avg_mood,
            COUNT(*) as days
        FROM records
        WHERE user_id = ?
        GROUP BY work_category
        """
        work_impact = self.execute(query_work, (user_id,), fetch=True)
        
        return overall, sleep_impact, work_impact
    
    def export_to_json(self, user_id, file_path):
        """Экспорт данных пользователя в JSON"""
        records = self.get_records_period(user_id, date(2000, 1, 1), date(2100, 1, 1))
        data = []
        for record in records:
            data.append({
                'date': str(record['record_date']),
                'mood': record['mood'],
                'work_hours': record['work_hours'],
                'sleep_hours': record['sleep_hours'],
                'comment': record['comment']
            })
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Данные экспортированы в {file_path}")
    
    def import_from_json(self, user_id, file_path):
        """Импорт данных из JSON"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for record in data:
            self.insert_or_update_record(
                user_id,
                date.fromisoformat(record['date']),
                record['mood'],
                record['work_hours'],
                record['sleep_hours'],
                record['comment']
            )
        logger.info(f"Данные импортированы из {file_path}")

    def close(self):
        """Закрывает соединение с БД"""
        if self.conn:
            self.conn.close()
            logger.info("Соединение с БД закрыто")
        if hasattr(self.local, 'conn') and self.local.conn:
            self.local.conn.close()
            self.local.conn = None
            