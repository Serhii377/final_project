import json
import re
from schemas import AIResponsePlan

try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


SYSTEM_PROMPT = """
Ти — AI-асистент для керування файлами. Відповідай ВИКЛЮЧНО валідним JSON без markdown-обгорток.
Дозволені дії (action):
- "list_files": показати файли (поле source — необов'язковий відносний шлях до папки)
- "search_files": пошук (поле query — фрагмент назви або розширення, напр. ".txt")
- "copy_file": копіювання (source — звідки, destination — куди)
- "move_file": переміщення (source — звідки, destination — куди)
- "rename_file": перейменування (source — поточний відносний шлях, destination — нова назва файлу)
- "read_text_file": читання/аналіз TXT, MD, CSV (source — відносний шлях до файлу)

Формат відповіді:
{
  "commands": [
    {
      "action": "назва_дії",
      "source": "шлях_або_null",
      "destination": "шлях_або_null",
      "query": "запит_або_null",
      "explanation": "коротке пояснення українською"
    }
  ]
}
"""


def generate_ai_plan(user_prompt: str, api_key: str) -> AIResponsePlan:
    if api_key.strip() and HAS_GENAI:
        client = genai.Client(api_key=api_key.strip())
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=f"{SYSTEM_PROMPT}\n\nЗапит користувача: {user_prompt}",
            config={"response_mime_type": "application/json"},
        )
        raw_json_text = response.text
    else:
        raw_json_text = _fallback_rule_based_json(user_prompt)

    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$", "", raw_json_text.strip(), flags=re.MULTILINE
    )
    data = json.loads(cleaned)
    return AIResponsePlan.model_validate(data)


def _fallback_rule_based_json(prompt: str) -> str:
    p = prompt.strip()
    low = p.lower()

    if low.startswith(("знайди", "пошук")):
        parts = p.split(maxsplit=1)
        q = parts[1] if len(parts) > 1 else ""
        cmd = {"action": "search_files", "query": q, "explanation": f"Пошук за запитом '{q}'"}
    elif low.startswith(("прочитай", "аналіз")):
        parts = p.split(maxsplit=1)
        src = parts[1] if len(parts) > 1 else ""
        cmd = {"action": "read_text_file", "source": src, "explanation": f"Читання та аналіз '{src}'"}
    elif low.startswith(("скопіюй", "копіювати")):
        parts = p.split()
        src = parts[1] if len(parts) > 1 else ""
        dst = parts[2] if len(parts) > 2 else ""
        cmd = {"action": "copy_file", "source": src, "destination": dst, "explanation": f"Копіювання {src} у {dst}"}
    elif low.startswith("перемісти"):
        parts = p.split()
        src = parts[1] if len(parts) > 1 else ""
        dst = parts[2] if len(parts) > 2 else ""
        cmd = {"action": "move_file", "source": src, "destination": dst, "explanation": f"Переміщення {src} у {dst}"}
    elif low.startswith("перейменуй"):
        parts = p.split()
        src = parts[1] if len(parts) > 1 else ""
        dst = parts[2] if len(parts) > 2 else ""
        cmd = {"action": "rename_file", "source": src, "destination": dst, "explanation": f"Перейменування {src} на {dst}"}
    else:
        cmd = {"action": "list_files", "source": None, "explanation": "Перегляд вмісту робочої папки"}

    return json.dumps({"commands": [cmd]}, ensure_ascii=False)
