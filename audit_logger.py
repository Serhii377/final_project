import csv
import sqlite3
from datetime import datetime
from typing import Optional


class AuditLogger:
    def __init__(self, db_path: str = "assistant_audit.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    source TEXT,
                    destination TEXT,
                    status TEXT NOT NULL,
                    details TEXT
                )
                """
            )

    def log(
        self,
        action: str,
        source: Optional[str],
        destination: Optional[str],
        status: str,
        details: str = "",
    ):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO operation_logs (timestamp, action, source, destination, status, details)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, action, source or "", destination or "", status, details),
            )

    def fetch_all(self) -> list[tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, timestamp, action, source, destination, status, details "
                "FROM operation_logs ORDER BY id DESC"
            )
            return cursor.fetchall()

    def export_csv(self, target_csv_path: str):
        rows = self.fetch_all()
        with open(target_csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(
                ["ID", "Час", "Операція", "Джерело", "Призначення", "Статус", "Деталі"]
            )
            writer.writerows(rows)
