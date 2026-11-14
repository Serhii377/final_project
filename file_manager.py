import csv
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class SafeFileManager:
    ALLOWED_TEXT_EXT = {".txt", ".md", ".csv"}
    MAX_READ_BYTES = 20 * 1024

    def __init__(self, workspace_dir: Path):
        self.workspace = workspace_dir.resolve()

    def safe_path(self, rel_path: Optional[str]) -> Path:
        if not rel_path or rel_path.strip() in ("", ".", "./", ".\\"):
            return self.workspace

        candidate = (self.workspace / rel_path).resolve()
        if not candidate.is_relative_to(self.workspace):
            raise PermissionError(
                f"Доступ заборонено! Шлях '{rel_path}' виходить за межі робочої папки."
            )
        return candidate

    def list_files(self, rel_dir: Optional[str] = None) -> list[dict[str, Any]]:
        target_dir = self.safe_path(rel_dir)
        if not target_dir.exists() or not target_dir.is_dir():
            raise FileNotFoundError(f"Папку не знайдено: {rel_dir or '.'}")

        items = []
        for entry in sorted(
            target_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
        ):
            stat = entry.stat()
            items.append(
                {
                    "name": entry.name,
                    "rel_path": str(entry.relative_to(self.workspace)),
                    "type": "Папка" if entry.is_dir() else "Файл",
                    "ext": entry.suffix.lower() if entry.is_file() else "",
                    "size": stat.st_size if entry.is_file() else 0,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                }
            )
        return items

    def search_files(self, query: str) -> list[dict[str, Any]]:
        q = query.strip().lower()
        results = []
        for entry in self.workspace.rglob("*"):
            if not entry.resolve().is_relative_to(self.workspace):
                continue
            if (
                q in entry.name.lower()
                or entry.suffix.lower() == q
                or f".{q}" == entry.suffix.lower()
            ):
                stat = entry.stat()
                results.append(
                    {
                        "name": entry.name,
                        "rel_path": str(entry.relative_to(self.workspace)),
                        "type": "Папка" if entry.is_dir() else "Файл",
                        "ext": entry.suffix.lower() if entry.is_file() else "",
                        "size": stat.st_size if entry.is_file() else 0,
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                            "%Y-%m-%d %H:%M"
                        ),
                    }
                )
        return results

    def read_and_analyze_text(self, rel_path: str) -> dict[str, Any]:
        target = self.safe_path(rel_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"Файл не знайдено: {rel_path}")

        ext = target.suffix.lower()
        if ext not in self.ALLOWED_TEXT_EXT:
            raise ValueError(
                f"Непідтримуваний формат '{ext}'. Дозволено лише: {', '.join(self.ALLOWED_TEXT_EXT)}"
            )

        size = target.stat().st_size
        if size > self.MAX_READ_BYTES:
            raise ValueError(
                f"Файл завеликий ({size} байт). Максимальний розмір: {self.MAX_READ_BYTES} байт (20 КБ)."
            )

        content = target.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        words = content.split()

        analysis: dict[str, Any] = {
            "file": str(target.relative_to(self.workspace)),
            "ext": ext,
            "size_bytes": size,
            "lines_count": len(lines),
            "words_count": len(words),
            "chars_count": len(content),
            "preview": content[:1500],
        }

        if ext == ".csv" and lines:
            rows = list(csv.reader(lines))
            analysis["csv_rows"] = len(rows)
            analysis["csv_columns"] = rows[0] if rows else []

        return analysis

    def copy_file(self, src_rel: str, dst_rel: str) -> str:
        src = self.safe_path(src_rel)
        dst = self.safe_path(dst_rel)
        if not src.exists() or not src.is_file():
            raise FileNotFoundError(f"Вихідний файл не знайдено: {src_rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return f"Скопійовано '{src.relative_to(self.workspace)}' -> '{dst.relative_to(self.workspace)}'"

    def move_file(self, src_rel: str, dst_rel: str) -> str:
        src = self.safe_path(src_rel)
        dst = self.safe_path(dst_rel)
        if not src.exists():
            raise FileNotFoundError(f"Об'єкт не знайдено: {src_rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Переміщено '{src_rel}' -> '{dst.relative_to(self.workspace)}'"

    def rename_file(self, src_rel: str, new_name: str) -> str:
        src = self.safe_path(src_rel)
        if not src.exists():
            raise FileNotFoundError(f"Об'єкт не знайдено: {src_rel}")
        if "/" in new_name or "\\" in new_name:
            raise ValueError("Для перейменування вкажіть лише нове ім'я файлу без шляху.")
        dst = self.safe_path(str(src.parent.relative_to(self.workspace) / new_name))
        src.rename(dst)
        return f"Перейменовано '{src.name}' -> '{dst.name}'"
