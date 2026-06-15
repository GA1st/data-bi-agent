import re

from core.logger import get_logger

logger = get_logger(__name__)

# Token estimation: Chinese ~2 tokens/char, English ~1.3 tokens/word
# This is a rough estimate — good enough for budgeting
_CHINESE_RE = re.compile(r'[一-鿿㐀-䶿]')


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    chinese_chars = len(_CHINESE_RE.findall(text))
    remaining = re.sub(r'[一-鿿]', '', text)
    english_words = len(remaining.split())
    return chinese_chars * 2 + int(english_words * 1.3) + 10


def _messages_tokens(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        total += 4  # role + separators overhead
        total += estimate_tokens(m.get("content", ""))
    return total


class ContextManager:
    """Manages conversation context with token budget control.

    Token budget is split into:
    - system_prompt_tokens: reserved for system prompt
    - history_tokens: available for conversation history
    - current_turn_tokens: reserved for the current user question + response

    When history exceeds budget, older turns are summarized.
    """

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens

    def build_messages(
        self,
        system_prompt: str,
        history: list[dict],
        current_question: str,
        history_summary: str | None = None,
    ) -> list[dict]:
        system_tokens = estimate_tokens(system_prompt)
        question_tokens = estimate_tokens(current_question)
        response_reserve = 1500
        history_budget = self.max_tokens - system_tokens - question_tokens - response_reserve

        if history_budget < 500:
            history_budget = 500

        messages = [{"role": "system", "content": system_prompt}]

        if history_summary:
            summary_tokens = estimate_tokens(history_summary)
            if summary_tokens < history_budget:
                messages.append({
                    "role": "system",
                    "content": f"[对话摘要]\n{history_summary}",
                })
                history_budget -= summary_tokens

        selected_history = self._select_history(history, history_budget)
        for h in selected_history:
            q = h.get("question", "")
            s = h.get("sql", "")
            messages.append({"role": "user", "content": q})
            messages.append({"role": "assistant", "content": s})

        messages.append({"role": "user", "content": current_question})

        total = _messages_tokens(messages)
        logger.debug(
            f"Context built: {len(selected_history)}/{len(history)} history turns, "
            f"~{total} tokens (budget {self.max_tokens})"
        )
        return messages

    def _select_history(self, history: list[dict], budget: int) -> list[dict]:
        selected = []
        used = 0
        for h in reversed(history):
            turn_tokens = estimate_tokens(h.get("question", "")) + estimate_tokens(h.get("sql", "")) + 8
            if used + turn_tokens > budget:
                break
            selected.insert(0, h)
            used += turn_tokens
        return selected

    def needs_summary(self, history: list[dict], threshold: int = 12) -> bool:
        return len(history) > threshold


async def summarize_history(history: list[dict], keep_last: int = 4) -> str:
    """Use LLM to compress older history into a summary."""
    from core.llm import chat

    old_turns = history[:-keep_last] if len(history) > keep_last else history
    if not old_turns:
        return ""

    turns_text = ""
    for h in old_turns:
        turns_text += f"用户: {h.get('question', '')}\nSQL: {h.get('sql', '')}\n\n"

    messages = [
        {
            "role": "system",
            "content": "你是对话摘要助手。将以下多轮数据分析对话压缩成简洁摘要，保留关键查询意图和SQL模式。用中文，不超过200字。",
        },
        {"role": "user", "content": turns_text},
    ]
    summary = await chat(messages, temperature=0)
    logger.info(f"History summarized: {len(old_turns)} turns -> {estimate_tokens(summary)} tokens")
    return summary
