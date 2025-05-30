import json
import os.path
import sys
from typing import List

from pydantic import BaseModel

version = 1
_abs_path: str = os.getcwd()


class _Base(BaseModel):
    log_level: str = ""
    order_script_name: str = ""


class _Uploader(BaseModel):
    user_agent: str = ""

    pixiv_csrf_token: str = ""
    pixiv_cookie: str = ""

    booth_csrf_token: str = ""
    booth_cookie: str = ""
    booth_authenticity_token: str = ""

    dropbox_access_token: str = ""

    unifans_auth_token: str = ""
    unifans_account_id: str = ""
    unifans_scheme_ids: List[str] = []


class _Tagger(BaseModel):
    translator: str = ""
    translator_app: str = ""
    translator_key: str = ""
    translator_language: str = ""
    global_remove_default_tags: list[str] = []
    global_add_default_tags: list[str] = []
    last_tags: list[str] = []
    front_tags: list[str] = []


class Configuration(BaseModel):
    base: _Base = _Base()
    uploader: _Uploader = _Uploader()
    tagger: _Tagger = _Tagger()
    http_proxy: str = "http://127.0.0.1:4275"


class Config:
    def __init__(self, configuration: Configuration):
        self._configuration = configuration
        self.abs_path = _abs_path
        self.log_level = configuration.base.log_level
        self.log_path: str = os.path.join(self.abs_path, "data\\log\\debug.log")
        self.order_script_name = configuration.base.order_script_name
        self.order_path: str = os.path.join(self.abs_path, "data\\orders")
        self.script_path: str = os.path.join(self.abs_path, "data\\script", self.order_script_name)

        self.translator: str = configuration.tagger.translator
        self.translator_app: str = configuration.tagger.translator_app
        self.translator_key: str = configuration.tagger.translator_key
        self.translator_language: str = configuration.tagger.translator_language
        self.global_remove_default_tags: list[str] = configuration.tagger.global_remove_default_tags
        self.global_add_default_tags: list[str] = configuration.tagger.global_add_default_tags
        self.last_tags: list[str] = configuration.tagger.last_tags
        self.front_tags: list[str] = configuration.tagger.front_tags

        self.user_agent = configuration.uploader.user_agent

        self.pixiv_csrf_token = configuration.uploader.pixiv_csrf_token
        self.pixiv_cookie = configuration.uploader.pixiv_cookie
        self.booth_csrf_token = configuration.uploader.booth_csrf_token
        self.booth_cookie = configuration.uploader.booth_cookie
        self.booth_authenticity_token = configuration.uploader.booth_authenticity_token
        self.dropbox_access_token = configuration.uploader.dropbox_access_token
        self.unifans_auth_token = configuration.uploader.unifans_auth_token
        self.unifans_account_id = configuration.uploader.unifans_account_id
        self.unifans_scheme_ids = configuration.uploader.unifans_scheme_ids

        self.http_proxy = configuration.http_proxy
        self.proxies = {
            "http": self.http_proxy,
            "https": self.http_proxy,
        }

        self.record_path: str = os.path.join(self.abs_path, "data\\log\\newly_record.json")
        self.record_comfyui_outputs_path: str = os.path.join(self.abs_path,
                                                             "data\\log\\newly_record_comfyui_outputs.json")

        self.output_path: str = os.path.join(self.abs_path, "data\\outputs")

        self.workflow_path: str = os.path.join(self.abs_path, "data\\workflow")
        self.workflow_name_sfw_name: str = "default_sfw.json"
        self.workflow_name_nsfw_censored_name: str = "default_nsfw_censored.json"
        self.workflow_name_nsfw_name: str = "default_nsfw.json"

        self.tagger_path: str = os.path.join(self.abs_path, "tagger.json")

        self.watermark_path: str = os.path.join(self.abs_path, "data\\watermark\\default.png")

        self.mosaic_model: str = os.path.join(self.abs_path, "data\\models\\censor.pt")


def loadConfig(path: str) -> Configuration:
    if not os.path.exists(path):
        raise FileNotFoundError(f"未发现config 文件路径: {path}")
    print(f"加载config文件路径: {path}")
    with open(path, mode="r", encoding="utf-8") as f:
        try:
            configuration = Configuration.parse_obj(json.load(f))
        except Exception as e:
            print(f"无效的config文件: {path}, {e}")
            sys.exit(1)
        return configuration


def createConfig(path: str):
    configInstance = Configuration()
    configString = configInstance.model_dump_json(indent=2)
    with open(path, "w", encoding="utf-8") as f:
        f.write(configString)


def initConfig():
    path = "data\\config.json"
    try:
        return loadConfig(path)
    except FileNotFoundError as _:
        createConfig(path)
        return loadConfig(path)


_configuration = initConfig()
config = Config(_configuration)

if __name__ == '__main__':
    createConfig(".\\config.json")
