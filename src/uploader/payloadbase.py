import os
from typing import List, Dict

from src import log


# 定义一个字典 'allow_website'，用于存储不同网站的特定配置。
# (保留原始定义，虽然在上传逻辑中不直接使用，但可能在其他地方引用)
class _Website:
    def __init__(self, packerEnable: bool = False, extensionFileContextEnable: bool = False):
        self.packerEnable: bool = packerEnable
        self.extensionFileContextEnable: bool = extensionFileContextEnable


_pixiv = _Website()
_booth = _Website(True, True)
_dropbox = _Website(True, True)
_unifans = _Website()
_test = _Website()

allowWebsite: Dict[str, _Website] = {
    "pixiv": _pixiv,
    "booth": _booth,
    "dropbox": _dropbox,
    "unifans": _unifans,
    "test": _test,
}


class PayloadBase:
    def __init__(self):
        self._files: List[str] = []
        self._fin: bool = False

    def append(self, filePath: str) -> bool:
        if os.path.exists(filePath):
            self._files.append(filePath)
            return True
        else:
            log.warn(f"上传的文件不存在: {filePath}")
            return False

    def extend(self, filePaths: List[str]) -> bool:
        for filePath in filePaths:
            if not os.path.exists(filePath):
                log.warn(f"上传的文件不存在:{filePath}")
                return False
            self._files.append(filePath)
        return True

    def getFiles(self) -> List[str]:
        return self._files
