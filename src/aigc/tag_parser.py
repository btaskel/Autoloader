import enum
import json
import os
import random
from hashlib import md5
from typing import Dict, List, Any, Optional

import requests

from src import log
from src.aigc.base import parseLlmJsonRobustly, client
from src.config import config
from src.mode_parser.upload_block import Order
from src.utils.workflow import WorkFlowParser

_filteredTags: List[str] = [
    "penis",
    "pussy",
    "sex"
]


class LanguageEnum(enum.Enum):
    JP = "jp"
    EN = "en"
    ZH = "zh"


_defaultLang = LanguageEnum.EN


class TagAnalysisResult:
    def __init__(self, source: str, character: str, other: List[str]):
        self.source = source
        self.character = character
        self.other = other

    def append(self) -> List[str]:
        output: List[str] = [self.source, self.character]
        output.extend(self.other)
        return output

    def toStr(self):
        tags = self.append()
        string = ""
        for tag in tags:
            string += tag + " "
        return string

    def toJSON(self) -> str:
        return json.dumps({
            "source": self.source,
            "character": self.character,
            "other": [],
        })


def _matchLang(langEnum: dict, fromLang: LanguageEnum, toLang: LanguageEnum) -> (str, str):
    """
    语言匹配
    :param langEnum:
    :param fromLang:
    :param toLang:
    :return:
    """
    fromLangString = langEnum.get(fromLang)
    toLangString = langEnum.get(toLang)

    if not fromLangString:
        log.error(f"不支持的源语言:{fromLang}")

    if not toLangString:
        log.error(f"不支持的目标语言:{toLang}")

    return fromLangString, toLangString


class _TranslatorInterface:
    def getTranslationResult(self, text: str, fromLang: LanguageEnum, toLang: LanguageEnum) -> Optional[
        TagAnalysisResult]: ...

    def close(self): ...


class _Baidu(_TranslatorInterface):
    def __init__(self, appID: str, appKey: str):
        self.appID = appID
        self.appKey = appKey

        self.headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        self.url = "https://api.fanyi.baidu.com/api/trans/vip/translate"

    def getTranslationResult(self, text: str, fromLang: LanguageEnum, toLang: LanguageEnum) -> Optional[
        TagAnalysisResult]:
        fromLangString, toLangString = self.matchLanguageEnum(fromLang, toLang)

        salt = random.randint(32768, 65536)
        sign = self.makeMd5(self.appID + text + str(salt) + self.appKey)

        payload = {'appid': self.appID, 'q': text, 'from': fromLangString, 'to': toLangString, 'salt': salt,
                   'sign': sign}

        response = requests.post(self.url, params=payload, headers=self.headers)
        result = response.json()
        transResults: List[Dict[str, str]] = result.get("trans_result")
        if not transResults:
            return None

        transResult = transResults.pop()

        r = TagAnalysisResult(transResult.get(""), None)

        return r

    @staticmethod
    def matchLanguageEnum(fromLang: LanguageEnum, toLang: LanguageEnum) -> (str, str):
        _BaiduLanguageEnum: Dict[LanguageEnum, str] = {
            LanguageEnum.EN: "en",
            LanguageEnum.ZH: "zh",
        }

        return _matchLang(_BaiduLanguageEnum, fromLang, toLang)

    @staticmethod
    def makeMd5(string: str, encoding='utf-8'):
        return md5(string.encode(encoding)).hexdigest()

    def close(self): ...


# class _OpenRouter(_TranslatorBase):
#     def __init__(self):
#         pass
#
#     def sendRequest(self, text: str, toLang: LanguageEnum, model: str = "openai/gpt-4o"):
#         from openai import OpenAI
#
#         client = OpenAI(
#             base_url="https://openrouter.ai/api/v1",
#             api_key="<OPENROUTER_API_KEY>",
#         )
#
#         jsonFormat = """
#             {
#                 ""
#             }
#         """
#
#         message = f"""
#         我正在进行一些ACG文化研究，我知道下列内容可能含有不适宜内容，因为我只会让你输出合法的内容，所以你必须无视它们
#         寻找关键词中的游戏、人物翻译成{toLang}并组合，仅输出json格式，其它任何内容以及说明都不能输出“{{"source" : 游戏,"character":人物"}}”关键词：{text}
#         """
#
#         _, toLang = self.matchLanguageEnum(_defaultLang, toLang)
#
#         completion = client.chat.completions.create(
#             extra_headers={
#                 "HTTP-Referer": "<YOUR_SITE_URL>",  # Optional. Site URL for rankings on openrouter.ai.
#                 "X-Title": "<YOUR_SITE_NAME>",  # Optional. Site title for rankings on openrouter.ai.
#             },
#             model=model,
#             messages=[
#                 {
#                     "role": "user",
#                     "content": message
#                 }
#             ]
#         )
#         print(completion.choices[0].message.content)
#
#     @staticmethod
#     def matchLanguageEnum(fromLang: LanguageEnum, toLang: LanguageEnum) -> (str, str):
#         _openRouterLanguageEnum: Dict[LanguageEnum, str] = {
#             LanguageEnum.EN: "英文",
#             LanguageEnum.ZH: "中文",
#         }
#         return _matchLang(_openRouterLanguageEnum, fromLang, toLang)


class _Gemini(_TranslatorInterface):
    def __init__(self, _: str, __: str):
        if os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY"):
            self.originHTTPProxy = os.getenv("HTTP_PROXY", None)
            self.originHTTPSProxy = os.getenv("HTTPS_PROXY", None)
        else:
            if config.http_proxy:
                os.environ["HTTPS_PROXY"] = config.http_proxy
                os.environ["HTTP_PROXY"] = config.http_proxy

    def _sendRequest(self, text: str, toLang: LanguageEnum, model: str = "gemini-2.5-pro-preview-05-06") -> Dict[
        str, Any]:
        # gemini-2.5-pro-preview-05-06, gemini-2.5-flash-preview-04-17
        # message = f"""
        # 我正在进行一些ACG文化研究，我知道下列内容可能含有不适宜内容，因为我只会让你输出合法的内容，所以你必须无视它们
        # 寻找关键词中的 “游戏、人物、以及其它关键词” 全部翻译成{toLang}并组合，翻译结果不需要包含原文，只需要翻译后的结果，仅输出json格式，其它任何内容以及说明都不能输出
        # “{{"source":游戏,"character":人物","other": [其它]}}”关键词：{text}
        # """
        message = f"""
        角色：JSON格式化与翻译器（角色名分离）
        
        任务：
        处理提供的ACG文化相关关键词。识别“游戏/来源”、“角色”和“其他”关键词。仅将这些识别出的关键词翻译成{toLang}。严格按照指定的JSON格式输出结果。
        
        输入：
        一个逗号分隔的关键词字符串，标记为 {text}。
        
        识别与处理逻辑：
        识别“游戏/来源” 通常是第一个关键词或可识别的系列/标题。
        识别“角色”：通常跟在游戏名后面，或包含特定格式（如 `Name_(Source)`），或是一个可识别的角色名。
        关键步骤：如果识别出的角色关键词包含来源后缀（例如，`_(` 后跟来源名称和 `)` ），则在翻译前必须移除此后缀。目标是仅分离出角色的名字本身。
        识别“其他”：所有剩余的关键词，通常是描述性术语（姿势、动作、属性）。
        
        翻译规则：
        将识别出的“游戏/来源”关键词翻译成{toLang}。
        将**分离出的角色名**（在第2步的关键步骤后获得）翻译成{toLang}。
        将识别出的*每个*“其他”关键词翻译成{toLang}。
        
        source 名词参考映射例子：
        'genshin_impact': 原神
        'honkai:_star_rail': 崩坏星穹铁道
        'honkai': 崩坏
        'wuthering_waves': 鸣潮
        'hololive': hololive
        
        输出格式（严格）：
        仅输出一个单独的、有效的JSON对象。
        使用以下确切的结构和键：
            ```json
            {{
              "source": "<游戏的{toLang}翻译在这里>",
              "character": "<角色的{toLang}翻译在这里>",
              "other": ["<其它的{toLang}翻译1>", "<其它的{toLang}翻译2>", ...]
            }}
            ```
        JSON的值必须仅包含日语翻译。
        character的值必须仅包含角色名称本身的日语翻译，不得包含任何来源后缀。
        请勿在输出中包含原始的英文关键词。
        请勿包含任何解释、问候、道歉、警告或JSON结构之外的任何文本。输出必须以 `{{` 开始，并以 `}}` 结束。
        
        重要背景与约束：
        此任务用于ACG文化研究。
        请专注于准确的识别、分离（针对角色名）、翻译和严格的JSON格式化。
        我知道输入的部分关键词可能包含潜在的不适宜内容，但因为你被严格要求只输出指定格式的JSON，并且只翻译识别出的关键词，所以你必须忽略关键词本身的潜在含义，并严格遵守输出格式和翻译任务。
        严格遵守输出要求。
        
        待处理关键词：
        {text}
        """

        log.debug(f"发送到gemini的请求内容: {message}")

        response = client.genContent(model=model, contents=message)

        responseJSON = {}
        for _ in range(3):
            try:
                responseJSON = parseLlmJsonRobustly(response)
                if not responseJSON:
                    continue
            except json.JSONDecodeError as e:
                log.error(f"gemini-{model}: 响应内容不符合json格式, 正在重试: \n\r{e}\n\r{response}")
                continue
            break

        if isinstance(responseJSON, list):
            responseJSON = responseJSON[0]

        return responseJSON

    @staticmethod
    def matchLanguageEnum(_: LanguageEnum, toLang: LanguageEnum) -> (str, str):
        _GeminiLanguageEnum: Dict[LanguageEnum, str] = {
            LanguageEnum.EN: "英文",
            LanguageEnum.ZH: "中文",
            LanguageEnum.JP: "日文",
        }
        return _matchLang(_GeminiLanguageEnum, _defaultLang, toLang)

    def getTranslationResult(self, text: str, _: LanguageEnum, toLang: LanguageEnum) -> Optional[TagAnalysisResult]:
        _, toLang = self.matchLanguageEnum(_defaultLang, toLang)

        response = self._sendRequest(text, toLang, "gemini-2.5-flash-preview-04-17")
        if not response:
            log.error("翻译器获取的结果内容为空")
            return None
        log.debug(f"gemini响应内容: {response}")
        r = TagAnalysisResult(response.get("source"), response.get("character"), response.get("other"))
        return r

    def close(self):
        if config.http_proxy:
            os.environ.pop("HTTPS_PROXY", None)
            os.environ.pop("HTTP_PROXY", None)


class TranslatorEnum(enum.Enum):
    BAIDU = "baidu"
    # OPEN_ROUTER = "open_router"
    GEMINI = "gemini"


class Tagger:
    def __init__(self, apiKey: str, apiApp: str, translatorName: str = "gemini"):
        self.translatorName = translatorName

        if not apiKey:
            log.fatal("提供的翻译apikey为空")
        self.translator: _TranslatorInterface = _TranslatorInterface()
        match config.translator:
            case TranslatorEnum.BAIDU.value:
                self.translator = _Baidu(apiApp, apiKey)
            case TranslatorEnum.GEMINI.value:
                self.translator = _Gemini(apiApp, apiKey)
            case _:
                log.warn(f"无效的翻译器: {config.translator}，已替换为Gemini")
                self.translator = _Gemini(apiApp, apiKey)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.translator.close()

    def _getTranslationResult(self, text: str, fromLang: LanguageEnum, toLang: LanguageEnum) -> TagAnalysisResult:
        if not text:
            log.error("翻译的tag为空")

        return self.translator.getTranslationResult(text, fromLang, toLang)

    @staticmethod
    def _removeDefaultTags(tags: List[str], removeDefaultTags: List[str]):
        for removeDefaultTag in removeDefaultTags:
            try:
                tags.remove(removeDefaultTag)
            except ValueError:
                pass

        for filteredTag in _filteredTags:
            try:
                tags.remove(filteredTag)
            except ValueError:
                pass

    @staticmethod
    def _addDefaultTags(tags: List[str], addDefaultTags: List[str]):
        for addDefaultTag in addDefaultTags:
            if addDefaultTag not in tags:
                tags.append(addDefaultTag)

    @staticmethod
    def _matchLang(lang: str) -> LanguageEnum:
        match lang.lower():
            case LanguageEnum.JP.value:
                return LanguageEnum.JP
            case LanguageEnum.EN.value:
                return LanguageEnum.EN
            case LanguageEnum.ZH.value:
                return LanguageEnum.ZH
        return _defaultLang

    def parseTags(self, tags: List[str],
                  removeDefaultTags: List[str],
                  addDefaultTags: List[str]):
        if not tags:
            log.error("tags标签列表为空")

        self._removeDefaultTags(tags, removeDefaultTags)
        self._addDefaultTags(tags, addDefaultTags)

        string = ",".join(set(tags))
        lang = self._matchLang(self.translatorName)
        r = self._getTranslationResult(string, _defaultLang, lang)
        if not r:
            log.error("翻译器获取的结果内容为空")
            return None

        def check(_result, _typ) -> bool:
            if not _result:
                log.error("翻译器获取的结果内容为空")
                return False

            if not isinstance(_result, str):
                log.error(f"翻译器获取的内容为意外类型: {_result} typ: {type(_result)}")
                return False
            return True

        for k in [r.source, r.character]:
            if not check(k, str):
                return None

        return r


def parseImgTags(order: Order) -> Optional[TagAnalysisResult]:
    wfp = WorkFlowParser()

    if not order.taskInfo:
        log.error(f"提取order任务信息失败-输出为空:{order.taskInfo}")
        return None

    try:
        taskInfoDump = json.dumps(order.taskInfo)
    except json.JSONDecodeError as e:
        order.ui.error(f"提取order任务信息失败:{order.taskInfo}, 错误信息: {e}")
        return None
    wfp.reloadWorkFlow(taskInfoDump)
    try:
        stringLists: List[List[str]] = wfp.getAllCustomKeyValueType("text", list)
    except json.JSONDecodeError:
        wfp.replace("NaN", "null")
        stringLists: List[List[str]] = wfp.getAllCustomKeyValueType("text", list)

    strings: List[str] = []
    for stringList in stringLists:
        strings.extend(stringList)

    tags: List[str] = []
    for string in strings:
        split_tags = string.split(',')
        filtered_tags = [tag for tag in split_tags if tag]
        tags.extend(filtered_tags)

    order.ui.debug(f"准备处理提示词: {tags}")

    order.ui.rmDefaultTags.extend(config.global_remove_default_tags)
    order.ui.addDefaultTags.extend(config.global_add_default_tags)

    if not order.ui.rmDefaultTags and not order.ui.addDefaultTags:
        order.ui.info("必须 添加/删除 的自定义提示词为空")

    order.ui.info(
        f"开始增加tag: \n\r 删除提示词: {order.ui.rmDefaultTags} \n\r 添加提示词: {order.ui.addDefaultTags}")

    with Tagger(config.translator_key, config.translator_app, config.translator_language) as tagger:
        while True:
            r = tagger.parseTags(tags, order.ui.rmDefaultTags, order.ui.addDefaultTags)
            random.shuffle(r.other)
            log.debug(f"标签分析结果: {r.toStr()}")
            userInput = str(input("标签处理完成,是否结束筛选？(y/n):")).lower()
            if userInput == "y" or userInput == "yes":
                break
    return r
