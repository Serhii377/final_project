from typing import Literal, Optional
from pydantic import BaseModel, Field


class FileCommand(BaseModel):
    action: Literal[
        "list_files",
        "search_files",
        "copy_file",
        "move_file",
        "rename_file",
        "read_text_file",
    ]
    source: Optional[str] = Field(
        default=None, description="Відносний шлях до файлу або підпапки"
    )
    destination: Optional[str] = Field(
        default=None, description="Відносний шлях призначення або нова назва"
    )
    query: Optional[str] = Field(
        default=None, description="Пошуковий запит (назва або розширення)"
    )
    explanation: str = Field(
        default="Виконання файлової операції",
        description="Коротке пояснення дії для користувача",
    )


class AIResponsePlan(BaseModel):
    commands: list[FileCommand]
