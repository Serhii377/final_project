import json
import os
from pathlib import Path
from typing import Any, Optional
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pydantic import ValidationError

from ai_service import generate_ai_plan
from audit_logger import AuditLogger
from file_manager import SafeFileManager
from schemas import FileCommand


class FileAssistantApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI-асистент для автоматизації роботи з файлами")
        self.geometry("1120x740")
        self.minsize(960, 640)

        self.logger = AuditLogger()
        self.file_manager: Optional[SafeFileManager] = None
        self.dry_run_var = tk.BooleanVar(value=True)
        self.api_key_var = tk.StringVar(value=os.getenv("GEMINI_API_KEY", ""))

        self._build_ui()

    def _build_ui(self):
        top_frame = ttk.LabelFrame(self, text="1. Робоче середовище (Sandbox)", padding=8)
        top_frame.pack(fill=tk.X, padx=10, pady=6)

        ttk.Button(top_frame, text="Обрати робочу папку...", command=self.select_workspace).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        self.workspace_lbl = ttk.Label(
            top_frame,
            text="Робочу папку не обрано",
            foreground="firebrick",
            font=("Segoe UI", 9, "bold"),
        )
        self.workspace_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(top_frame, text="Gemini API Key (опц.):").pack(side=tk.LEFT, padx=(10, 4))
        ttk.Entry(top_frame, textvariable=self.api_key_var, width=26, show="*").pack(side=tk.LEFT)

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        left_frame = ttk.LabelFrame(paned, text="2. Вміст робочої папки", padding=8)
        paned.add(left_frame, weight=3)

        search_bar = ttk.Frame(left_frame)
        search_bar.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(search_bar, text="Пошук (назва / .ext):").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_bar)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self.search_entry.bind("<Return>", lambda e: self.search_files_ui())

        ttk.Button(search_bar, text="Знайти", command=self.search_files_ui).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_bar, text="Скинути / Оновити", command=self.refresh_file_table).pack(
            side=tk.LEFT, padx=2
        )

        columns = ("name", "type", "ext", "size", "modified", "rel_path")
        self.tree = ttk.Treeview(left_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("name", text="Назва")
        self.tree.heading("type", text="Тип")
        self.tree.heading("ext", text="Розширення")
        self.tree.heading("size", text="Розмір (Б)")
        self.tree.heading("modified", text="Змінено")
        self.tree.heading("rel_path", text="Відносний шлях")

        self.tree.column("name", width=180)
        self.tree.column("type", width=65, anchor=tk.CENTER)
        self.tree.column("ext", width=80, anchor=tk.CENTER)
        self.tree.column("size", width=85, anchor=tk.E)
        self.tree.column("modified", width=115, anchor=tk.CENTER)
        self.tree.column("rel_path", width=170)

        tree_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        right_frame = ttk.LabelFrame(
            paned, text="3. AI-асистент (JSON-команди) та аналіз файлів", padding=8
        )
        paned.add(right_frame, weight=2)

        ttk.Label(
            right_frame,
            text="Введіть завдання природною мовою\n(або без API: 'знайди .txt', 'прочитай notes.txt', 'перейменуй a.txt b.txt'):",
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        self.prompt_text = tk.Text(right_frame, height=4, wrap=tk.WORD, font=("Segoe UI", 9))
        self.prompt_text.pack(fill=tk.X, pady=4)

        ctrl_row = ttk.Frame(right_frame)
        ctrl_row.pack(fill=tk.X, pady=4)

        ttk.Checkbutton(
            ctrl_row,
            text="Режим Dry-Run (лише план без виконання)",
            variable=self.dry_run_var,
        ).pack(side=tk.LEFT)

        ttk.Button(ctrl_row, text="Виконати AI-запит", command=self.run_ai_request).pack(
            side=tk.RIGHT
        )

        ttk.Label(right_frame, text="Результат роботи, JSON-план та аналіз файлів:").pack(
            anchor=tk.W, pady=(6, 2)
        )
        self.output_box = scrolledtext.ScrolledText(
            right_frame, height=16, wrap=tk.WORD, font=("Consolas", 9), state=tk.DISABLED
        )
        self.output_box.pack(fill=tk.BOTH, expand=True)

        bottom_frame = ttk.LabelFrame(self, text="4. Журнал виконаних операцій (SQLite)", padding=6)
        bottom_frame.pack(fill=tk.X, padx=10, pady=(2, 8))

        ttk.Button(
            bottom_frame, text="Переглянути журнал операцій", command=self.show_logs_window
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            bottom_frame, text="Експортувати журнал у CSV...", command=self.export_logs_csv
        ).pack(side=tk.LEFT)
        self.status_lbl = ttk.Label(bottom_frame, text="Готово до роботи.")
        self.status_lbl.pack(side=tk.RIGHT)

    def append_output(self, text: str, clear: bool = False):
        self.output_box.configure(state=tk.NORMAL)
        if clear:
            self.output_box.delete("1.0", tk.END)
        self.output_box.insert(tk.END, text + "\n")
        self.output_box.see(tk.END)
        self.output_box.configure(state=tk.DISABLED)

    def select_workspace(self):
        folder = filedialog.askdirectory(title="Оберіть робочу папку")
        if not folder:
            return
        self.file_manager = SafeFileManager(Path(folder))
        self.workspace_lbl.configure(
            text=f"Активна папка: {self.file_manager.workspace}", foreground="darkgreen"
        )
        self.refresh_file_table()
        self.append_output(
            f"[OK] Встановлено робочу папку: {self.file_manager.workspace}", clear=True
        )

    def populate_table(self, items: list[dict[str, Any]]):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in items:
            self.tree.insert(
                "",
                tk.END,
                values=(
                    item["name"],
                    item["type"],
                    item["ext"],
                    item["size"],
                    item["modified"],
                    item["rel_path"],
                ),
            )

    def refresh_file_table(self):
        if not self.file_manager:
            return
        try:
            items = self.file_manager.list_files()
            self.populate_table(items)
            self.status_lbl.configure(text=f"Елементів у корені: {len(items)}")
        except Exception as e:
            messagebox.showerror("Помилка", str(e))

    def search_files_ui(self):
        if not self.file_manager:
            messagebox.showwarning("Увага", "Спочатку оберіть робочу папку.")
            return
        q = self.search_entry.get().strip()
        if not q:
            self.refresh_file_table()
            return
        try:
            results = self.file_manager.search_files(q)
            self.populate_table(results)
            self.status_lbl.configure(text=f"Знайдено за запитом '{q}': {len(results)}")
        except Exception as e:
            messagebox.showerror("Помилка пошуку", str(e))

    def on_tree_double_click(self, event):
        if not self.file_manager:
            return
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        item_type, rel_path = values[1], values[5]
        if item_type == "Файл":
            try:
                analysis = self.file_manager.read_and_analyze_text(rel_path)
                self._display_file_analysis(analysis)
            except Exception as e:
                messagebox.showinfo("Інформація", str(e))

    def _display_file_analysis(self, analysis: dict[str, Any]):
        report = [
            f"=== АНАЛІЗ ФАЙЛУ: {analysis['file']} ===",
            f"Формат: {analysis['ext']} | Розмір: {analysis['size_bytes']} байт",
            f"Рядків: {analysis['lines_count']} | Слів: {analysis['words_count']} | Символів: {analysis['chars_count']}",
        ]
        if "csv_rows" in analysis:
            report.append(
                f"CSV рядків: {analysis['csv_rows']} | Колонки: {analysis['csv_columns']}"
            )
        report.append("--- Попередній перегляд вмісту ---")
        report.append(analysis["preview"])
        report.append("=" * 40)
        self.append_output("\n".join(report))

    def run_ai_request(self):
        if not self.file_manager:
            messagebox.showwarning("Увага", "Спочатку оберіть робочу папку!")
            return

        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showwarning("Увага", "Введіть текстовий запит для AI.")
            return

        try:
            plan = generate_ai_plan(prompt, self.api_key_var.get())
        except (json.JSONDecodeError, ValidationError) as e:
            messagebox.showerror("Помилка валідації JSON від AI", f"Некоректна схема:\n{e}")
            return
        except Exception as e:
            messagebox.showerror("Помилка звернення до AI", str(e))
            return

        is_dry_run = self.dry_run_var.get()
        self.append_output(
            f"\n>>> ЗАПИТ: {prompt}\n>>> РЕЖИМ: {'DRY-RUN (попередній перегляд)' if is_dry_run else 'ВИКОНАННЯ'}",
            clear=True,
        )
        self.append_output("Отриманий валідний JSON-план:\n" + plan.model_dump_json(indent=2))

        if is_dry_run:
            self.append_output("\n[DRY-RUN] План сформовано. Жодних змін на диску не виконано.")
            for idx, cmd in enumerate(plan.commands, 1):
                self.append_output(
                    f"  Крок {idx}: {cmd.action} | src={cmd.source} | dst={cmd.destination} | query={cmd.query}"
                )
                self.logger.log(cmd.action, cmd.source, cmd.destination, "DRY_RUN", cmd.explanation)
            return

        for cmd in plan.commands:
            self._execute_single_command(cmd)

        self.refresh_file_table()

    def _requires_confirmation(self, cmd: FileCommand) -> tuple[bool, str]:
        assert self.file_manager is not None
        reasons = []

        if cmd.action == "move_file":
            reasons.append("Переміщення файлу/папки")
        elif cmd.action == "rename_file":
            reasons.append("Перейменування об'єкта")

        if cmd.action in ("copy_file", "move_file") and cmd.destination:
            dst_path = self.file_manager.safe_path(cmd.destination)
            if dst_path.exists():
                reasons.append(
                    f"УВАГА: Цільовий файл '{cmd.destination}' вже існує і буде ПЕРЕЗАПИСАНИЙ!"
                )
        elif cmd.action == "rename_file" and cmd.source and cmd.destination:
            src_path = self.file_manager.safe_path(cmd.source)
            dst_path = self.file_manager.safe_path(
                str(src_path.parent.relative_to(self.file_manager.workspace) / cmd.destination)
            )
            if dst_path.exists():
                reasons.append(
                    f"УВАГА: Файл '{cmd.destination}' вже існує і буде ПЕРЕЗАПИСАНИЙ!"
                )

        return (len(reasons) > 0, "\n".join(reasons))

    def _execute_single_command(self, cmd: FileCommand):
        assert self.file_manager is not None
        try:
            need_confirm, warning_text = self._requires_confirmation(cmd)
            if need_confirm:
                details = (
                    f"Запланована дія: {cmd.action}\n"
                    f"Пояснення AI: {cmd.explanation}\n"
                    f"Джерело: {cmd.source}\n"
                    f"Призначення: {cmd.destination}\n\n"
                    f"Причина підтвердження:\n{warning_text}\n\n"
                    f"Підтвердити виконання цієї операції?"
                )
                approved = messagebox.askyesno("Підтвердження небезпечної операції", details)
                if not approved:
                    msg = f"Скасовано користувачем: {cmd.action} ({cmd.source} -> {cmd.destination})"
                    self.append_output(f"[СКАСОВАНО] {msg}")
                    self.logger.log(cmd.action, cmd.source, cmd.destination, "CANCELLED", msg)
                    return

            if cmd.action == "list_files":
                items = self.file_manager.list_files(cmd.source)
                self.populate_table(items)
                res_msg = f"Показано {len(items)} елементів у '{cmd.source or '.'}'"
            elif cmd.action == "search_files":
                if not cmd.query:
                    raise ValueError("Не вказано пошуковий запит (query).")
                items = self.file_manager.search_files(cmd.query)
                self.populate_table(items)
                res_msg = f"Знайдено {len(items)} збігів за запитом '{cmd.query}'"
            elif cmd.action == "read_text_file":
                if not cmd.source:
                    raise ValueError("Не вказано файл для читання (source).")
                analysis = self.file_manager.read_and_analyze_text(cmd.source)
                self._display_file_analysis(analysis)
                res_msg = f"Проаналізовано файл '{cmd.source}'"
            elif cmd.action == "copy_file":
                if not cmd.source or not cmd.destination:
                    raise ValueError("Для copy_file потрібні source та destination.")
                res_msg = self.file_manager.copy_file(cmd.source, cmd.destination)
            elif cmd.action == "move_file":
                if not cmd.source or not cmd.destination:
                    raise ValueError("Для move_file потрібні source та destination.")
                res_msg = self.file_manager.move_file(cmd.source, cmd.destination)
            elif cmd.action == "rename_file":
                if not cmd.source or not cmd.destination:
                    raise ValueError("Для rename_file потрібні source та destination.")
                res_msg = self.file_manager.rename_file(cmd.source, cmd.destination)
            else:
                raise ValueError(f"Невідома команда: {cmd.action}")

            self.append_output(f"[ВИКОНАНО] {res_msg}")
            self.logger.log(cmd.action, cmd.source, cmd.destination, "SUCCESS", res_msg)

        except Exception as e:
            err_msg = f"Помилка при виконанні {cmd.action}: {e}"
            self.append_output(f"[ПОМИЛКА] {err_msg}")
            self.logger.log(cmd.action, cmd.source, cmd.destination, "ERROR", str(e))

    def show_logs_window(self):
        win = tk.Toplevel(self)
        win.title("Журнал операцій (SQLite)")
        win.geometry("860x420")

        cols = ("id", "timestamp", "action", "source", "destination", "status", "details")
        log_tree = ttk.Treeview(win, columns=cols, show="headings")
        headers = {
            "id": ("ID", 40),
            "timestamp": ("Час", 130),
            "action": ("Операція", 110),
            "source": ("Джерело", 130),
            "destination": ("Призначення", 130),
            "status": ("Статус", 90),
            "details": ("Деталі", 210),
        }
        for col, (title, width) in headers.items():
            log_tree.heading(col, text=title)
            log_tree.column(col, width=width)

        for row in self.logger.fetch_all():
            log_tree.insert("", tk.END, values=row)

        log_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def export_logs_csv(self):
        save_path = filedialog.asksaveasfilename(
            title="Експорт журналу в CSV",
            defaultextension=".csv",
            filetypes=[("CSV файли", "*.csv")],
            initialfile="file_assistant_logs.csv",
        )
        if not save_path:
            return
        try:
            self.logger.export_csv(save_path)
            messagebox.showinfo("Експорт завершено", f"Журнал успішно збережено у:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Помилка експорту", str(e))
