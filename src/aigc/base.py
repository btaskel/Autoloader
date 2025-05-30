import json
import re
from typing import Dict, Any, Optional

import google.genai
from google.genai import Client as geminiClient

from src import log
from src.config import config

gemini: Optional[geminiClient] = None


# 初始化Google Gemini客户端


class Client:
    def __init__(self):
        if config.translator.lower() == "gemini":
            self.gemini = google.genai.Client(api_key=config.translator_key)
        else:
            log.fatal("未有可用的llm翻译器")

    def genContent(self, model: str, contents: str) -> Optional[str]:
        if self.gemini:
            return self.gemini.models.generate_content(model=model, contents=contents).text
        else:
            log.fatal("未有可用的llm翻译器")
            return None

    def genStreamContent(self, model: str, contents: str) -> List[str]:
        if self.gemini:
            return self.gemini.models.generate_content_stream(model=model, contents=contents)
        else:
            log.fatal("未有可用的llm翻译器")
            return None


client: Optional[Client] = Client()


def parseLlmJsonRobustly(LLMOutput: str) -> Dict[str, Any] | None:
    """
    健壮地尝试从可能包含干扰文本的字符串中解析 JSON 对象或列表。

    Args:
        LLMOutput: LLM 返回的原始字符串。

    Returns:
        如果成功解析，则返回解析后的 Python 对象 (通常是 dict 或 list)。
        如果无法提取或解析 JSON，则返回 None。
    """
    if not isinstance(LLMOutput, str):
        log.error(f"输入不是字符串，而是 {type(LLMOutput)}: {LLMOutput}")
        return None

    if not LLMOutput:
        log.warn("输入字符串为空。")
        return None

    match = re.search(r'```json\s*(\{.*}|\[.*])\s*```', LLMOutput, re.DOTALL | re.IGNORECASE)
    if match:
        potential_json = match.group(1)
        log.debug("从 Markdown 代码块中提取了潜在 JSON。")
    else:
        start_brace = LLMOutput.find('{')
        start_bracket = LLMOutput.find('[')

        if start_brace == -1 and start_bracket == -1:
            log.warn(f"未能在字符串中找到 JSON 的起始 '{{' 或 '[': {LLMOutput[:100]}...")  # 只记录前 100 个字符
            return None

        # 选择第一个出现的起始符号
        if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
            start_index = start_brace
            end_char = '}'
        else:
            start_index = start_bracket
            end_char = ']'

        end_index = LLMOutput.rfind(end_char)

        if end_index == -1 or end_index < start_index:
            log.warn(f"未能找到与起始符号匹配的 JSON 结束 '{end_char}': {LLMOutput[:100]}...")
            return None

        potential_json = LLMOutput[start_index: end_index + 1]
        log.debug("通过查找首尾括号/方括号提取了潜在 JSON。")

    potential_json = potential_json.strip()
    if not potential_json:
        log.warn("提取和清理后，潜在 JSON 字符串为空。")
        return None

    try:
        parsedData = json.loads(potential_json)
        log.debug("JSON 解析成功。")
        return parsedData
    except json.JSONDecodeError as e:
        log.error(f"JSON 解析失败: {e}")
        log.error(f"失败的 JSON 字符串 (已提取和清理): {potential_json}")

        return None  # 标准解析失败后返回 None
