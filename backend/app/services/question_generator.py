from .local_models import LocalModelManager
from typing import List, Optional


class QuestionGenerator:
    def __init__(self, model_manager: Optional[LocalModelManager] = None):
        self.mm = model_manager or LocalModelManager()

    def _template(self, style: str, topic_summary: str) -> str:
        if style == 'deep_psych':
            return f"Based on the following short conversation summary: {topic_summary}\n\nSuggest one short, deep psychological question that explores feelings or motivations. Keep it open-ended." 
        if style == 'quirky':
            return f"Given this conversation about {topic_summary}, suggest a quirky, funny, or light-hearted question to keep things playful." 
        if style == 'clarifying':
            return f"Given this short summary: {topic_summary}, suggest one clarifying or follow-up question to dig deeper into specifics." 
        # default
        return f"Given this: {topic_summary}, suggest one interesting open-ended question."

    def generate(self, topic_summary: str, style: str = 'deep_psych', num: int = 3) -> List[str]:
        prompt = self._template(style, topic_summary)
        try:
            outs = self.mm.generate(prompt, max_length=64, num_return_sequences=num)
            # filter None
            return [o for o in outs if o]
        except Exception:
            # fallback: return simple templated questions
            if style == 'deep_psych':
                return [f"How does {topic_summary.split()[0]} make you feel?"]
            return [f"Tell me more about {topic_summary}"]


__all__ = ['QuestionGenerator']
