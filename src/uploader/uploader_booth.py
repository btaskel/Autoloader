import datetime
import json
import os.path
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

import requests

from src import log
from src.config import config
from src.uploader.payloadbase import PayloadBase

BASE_URL_MANAGE = "https://manage.booth.pm"
BASE_URL_SHOP = "https://kragoe2.booth.pm"


class BoothPostInfo(PayloadBase):
    def __init__(self):
        super().__init__()
        self.description: str = ""
        self.name: str = ""
        self.adult: bool = False
        self.stock: int = 0
        self.price: int = 0
        self.allocatable_stock: int = 0
        self.tagsArray: List[str] = []

    def extend(self, filePaths: List[str]) -> bool:
        """
        Appends a list of file paths to the internal list.
        Ensures each file exists and renames files if their basename exceeds 50 characters.

        Args:
            filePaths: A list of file paths to add.

        Returns:
            True if all files were successfully processed (existed and renamed if necessary),
            False otherwise.
        """
        processed_files = []  # Store paths to add after successful processing/renaming
        for original_filePath in filePaths:
            if not os.path.exists(original_filePath):
                log.warn(f"上传的文件不存在:{original_filePath}")
                return False  # Fail fast if any file doesn't exist

            filename = os.path.basename(original_filePath)
            current_filePath = original_filePath  # Track the path to be added

            if len(filename) > 50:
                log.info(f"文件名 '{filename}' 长度 ({len(filename)}) 超过50个字符，将进行重命名。")
                try:
                    base, ext = os.path.splitext(filename)

                    # Ensure extension itself isn't too long
                    if len(ext) >= 50:
                        log.error(f"文件 '{filename}' 的扩展名过长 ({len(ext)} >= 50)，无法处理。")
                        return False  # Cannot proceed

                    # Calculate allowed length for the base name, ensuring total is <= 50
                    # The +1 accounts for the dot in the extension, but splitext includes it.
                    allowed_base_len = 50 - len(ext)

                    # This check should be redundant if len(ext) < 50 and len(filename) > 50,
                    # but it's a safeguard.
                    if allowed_base_len <= 0:
                        log.error(f"无法为文件 '{filename}' 生成有效短名称（扩展名过长）。")
                        return False

                    truncated_base = base[:allowed_base_len]
                    new_filename = truncated_base + ext

                    # Ensure the new name is actually shorter (edge case: truncation didn't change length)
                    if len(new_filename) > 50:
                        # This might happen if allowed_base_len calculation was off or ext is exactly 50
                        log.error(f"尝试重命名 '{filename}' 为 '{new_filename}' 失败，新文件名仍然过长。")
                        # Fallback: Force truncate the whole new name? Risky. Let's fail.
                        return False

                    # Construct the full new path
                    dir_path = os.path.dirname(original_filePath)
                    new_filePath = os.path.join(dir_path, new_filename)

                    # Avoid overwriting existing files with the new name
                    if os.path.exists(new_filePath):
                        # Simple collision handling: log error and fail.
                        # More robust handling might involve adding suffixes (_1, _2, etc.)
                        log.error(f"重命名失败：目标文件 '{new_filePath}' 已存在。")
                        return False

                    # Perform the rename
                    log.info(f"重命名 '{original_filePath}' 为 '{new_filePath}'")
                    os.rename(original_filePath, new_filePath)
                    current_filePath = new_filePath  # Use the new path going forward

                except OSError as e:
                    log.error(f"重命名文件 '{original_filePath}' 失败: {e}")
                    return False  # Renaming failed, stop processing this batch

            # Add the final path (original or renamed) to the list for this batch
            processed_files.append(current_filePath)

        # If all files in the list were processed successfully, extend the main list
        self._files.extend(processed_files)
        return True


class BoothUploader:
    def __init__(self, csrfToken: str, cookieString: str, userAgent: str, authenticityToken: str):
        self.csrfToken: str = csrfToken
        self.cookieString: str = cookieString
        self.userAgent: str = userAgent
        self.authenticityToken: str = authenticityToken

        self._session: requests.Session = self._initSession()

        self._tz = datetime.timezone(offset=datetime.timedelta(hours=9), name='JST/KST')

    def _initSession(self) -> requests.Session:
        """创建并配置用于 Booth API 请求的 Session 对象"""
        s = requests.Session()

        if config.http_proxy:
            s.proxies = config.proxies

        s.headers.update({
            "User-Agent": self.userAgent,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",  # 可以考虑改为 zh-CN 或根据需要调整
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Gpc": "1",
            "Cookie": self.cookieString,
            "X-Csrf-Token": self.csrfToken,
            "sec-ch-ua": "\"Brave\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
        })
        return s

    def _makeAPIRequest(
            self,
            method: str,
            url: str,
            payload: Optional[Dict[str, Any]] = None,
            filesData: Optional[Dict[str, Any]] = None,
            request_description: str = "API request"
    ) -> Optional[Dict[str, Any]]:
        """
        发送 API 请求并处理基本响应和错误。

        Args:
            method: HTTP 方法 (e.g., "PATCH", "POST").
            url: 请求的 URL.
            payload: 请求体 (JSON).
            request_description: 用于日志输出的请求描述.

        Returns:
            成功时返回响应的 JSON 数据 (字典)，失败时返回 None.
        """
        log.info(f"[*] Sending {method.upper()} request to {request_description}: {url}")
        headers = self._session.headers.copy()
        if filesData:
            headers.pop('Content-Type', None)
        else:
            headers['Content-Type'] = 'application/json'
        headers['Sec-Fetch-Site'] = 'same-origin'  # 特定于这两个请求

        try:
            response = self._session.request(method, url, json=payload, headers=headers, files=filesData)
            response.raise_for_status()  # 检查 HTTP 错误 (4xx, 5xx)

            log.info(f"[+] {method.upper()} request successful (Status Code: {response.status_code})")
            try:
                response_json = response.json()
                # log.info(f"    Response JSON: {json.dumps(response_json, indent=2, ensure_ascii=False)}") # 格式化打印 JSON
                return response_json
            except json.JSONDecodeError:
                log.info(f"    Response Text: {response.text}")
                return {"raw_text": response.text}  # 或者返回一个包含原始文本的字典

        except requests.exceptions.RequestException as e:
            log.error(f"{method.upper()} request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                log.info(f"    Status Code: {e.response.status_code}")
                # 尝试解析错误响应体 (可能是 JSON)
                try:
                    error_details = e.response.json()
                    log.info(f"    Error Body: {json.dumps(error_details, indent=2, ensure_ascii=False)}")
                except json.JSONDecodeError:
                    log.info(f"    Error Body: {e.response.text}")
            return None  # 表示请求失败

    @staticmethod
    def _makeItemUpdateURL(itemId: int) -> str:
        return urljoin(BASE_URL_MANAGE, f"/items/{itemId}")

    @staticmethod
    def _makeVariationsURL(itemId: int) -> str:
        """获取更新商品规格/变体的 API URL"""
        return urljoin(BASE_URL_MANAGE, f"/items/{itemId}/variations")

    @staticmethod
    def _makeRefererURL(itemId: int) -> str:
        return urljoin(BASE_URL_MANAGE, f"/items/{itemId}/edit")

    @staticmethod
    def _makePostImageURL(itemId: int) -> str:
        return urljoin(BASE_URL_MANAGE, f"/items/{itemId}/images")

    @staticmethod
    def _makePostDownloadablesURL(itemId: int) -> str:
        return urljoin(BASE_URL_MANAGE, f"/items/{itemId}/downloadables")

    def _getNowTime(self) -> str:
        nowAware = datetime.datetime.now(self._tz)
        return nowAware.isoformat(sep='T', timespec='milliseconds')

    def _uploadImgResource(self, filePath: str, itemId: int) -> dict[str, Any] | None:
        filename = os.path.basename(filePath)
        filesData = {
            "image[file]": (filename, open(filePath, 'rb'), "image/png")
        }
        postImgURL = self._makePostImageURL(itemId)
        return self._makeAPIRequest("POST", postImgURL, None, filesData, "_uploadImgResource")

    def _uploadDownloadableResource(self, filePath: str, itemId: int) -> dict:
        filename = os.path.basename(filePath)
        filesData = {
            "downloadable[file]": (filename, open(filePath, 'rb'), "application/octet-stream")
        }
        postDownloadablesURL = self._makePostDownloadablesURL(itemId)
        return self._makeAPIRequest("POST", postDownloadablesURL, None, filesData, "_uploadDownloadableResource")

    def _createItemVariations(self,
                              itemId: int,
                              payload: BoothPostInfo,
                              downloadableIds: List[int]
                              ) -> dict:
        itemUpdateURL = self._makeItemUpdateURL(itemId)
        result = self._makeAPIRequest("GET", itemUpdateURL, None, None, "createItemVariations")
        variations: List[dict] = result.get("variations")
        variation = variations.pop()
        varId = variation.get("id")

        now = self._getNowTime()
        # {
        #     "variations": [
        #         {
        #             "id": variation_id,  # 使用传入的变体 ID
        #             "name": "default",  # 变体名称可能也需要参数化
        #             "type": "direct",
        #             "stock": stock,  # 使用传入的库存
        #             "price": price,  # 使用传入的价格
        #             "margin": None,
        #             "production_cost": None,
        #             "item_id": int(item_id),
        #             "display_order": 0,
        #             "mailbin_enabled": None,
        #             "tying_musics": False,
        #             "factory_item_group_id": None,
        #             "factory_book_id": None,
        #             "allocatable_stock": 0,
        #             "downloadable_ids": [],
        #             "min_margin": 0,
        #             "use_mailbin?": False,
        #             "waiting_on_arrival?": False,
        #             "key": str(variation_id)  # key 通常和 id 相同
        #         }
        #         # 如果需要更新多个变体，可以在这里扩展逻辑
        #     ]
        # }

        variation = {
            "variations": [
                {
                    "id": varId,
                    "name": "default",
                    "type": "digital",
                    "stock": payload.stock,
                    "price": payload.price,
                    "margin": None,
                    "production_cost": None,
                    "item_id": itemId,
                    "display_order": 0,
                    "mailbin_enabled": None,
                    "tying_musics": True,
                    "factory_item_group_id": None,
                    "factory_book_id": None,
                    "created_at": now,
                    "updated_at": now,
                    "allocatable_stock": 1,
                    "downloadable_ids": [
                        # 6546252 下载
                    ],
                    "min_margin": 0,
                    "use_mailbin?": False,
                    "waiting_on_arrival?": False,
                    "key": str(varId)
                }
            ]
        }
        variation["variations"][-1]["downloadable_ids"].extend(downloadableIds)

        return variation

    def _getItemUpdatePayload(self,
                              itemId: int,
                              shopId: int,
                              payload: BoothPostInfo) -> (dict, list[int]):
        itemDc = {
            "item": {
                "id": itemId,
                "description": payload.description,
                "state": "draft",
                "price": payload.price,
                "shop_id": shopId,
                "name": payload.name,
                "page_design": "{\"modules\":[]}",
                "package_size_id": 1,
                "adult": 1 if payload.adult else 0,
                "accept_proxy_shipping": "refused",
                "category_id": 148,
                "preorder_enabled": False,
                "purchase_limit": 0,
                "shipping_date": None,
                "tags_array": payload.tagsArray,
                "sound": None,
                "downloadables": [
                    #   {
                    #   "id": 6546252,
                    #   "item_id": 6825688,
                    #   "name": "Screenshot_2025-04-19_171520.png",
                    #   "display_order": 0,
                    #   "download_count": 0,
                    #   "optional_files": [],
                    #   "file_size": 401,
                    #   "created_at": "2025-04-20T19:34:55.000+09:00",
                    #   "updated_at": "2025-04-20T19:34:55.000+09:00",
                    #   "deleted_at": None,
                    #   "url": "https://manage.booth.pm/items/6825688/downloadables/6546252"
                    # }
                ],
                "url": f"https://{BASE_URL_SHOP}/items/{itemId}",
                "published_at_str": None,
                "event_ids": [],
                "item_message_for_twitter": " | kragoe",
                "anshin_booth_pack_package_sizes": [
                    {
                        "id": 16,
                        "label": "yamato_anonymous_post",
                        "name": "あんしんBOOTHパック ネコポス",
                        "short_name": "ネコポス",
                        "anshin_booth_pack": True,
                        "price_str": "370 JPY",
                        "min_price": 370,
                        "min_price_str": "370 JPY",
                        "max_price": 370,
                        "max_price_str": "370 JPY"
                    }, {
                        "id": 17,
                        "label": "yamato_anonymous_compact",
                        "name": "あんしんBOOTHパック 宅急便コンパクト",
                        "short_name": "宅急便コンパクト",
                        "anshin_booth_pack": True,
                        "price_str": "540 JPY 〜 1,090 JPY",
                        "min_price": 540,
                        "min_price_str": "540 JPY",
                        "max_price": 1090,
                        "max_price_str": "1,090 JPY"
                    }, {
                        "id": 18,
                        "label": "yamato_anonymous_box_60",
                        "name": "あんしんBOOTHパック 宅急便60サイズ",
                        "short_name": "宅急便60サイズ",
                        "anshin_booth_pack": True,
                        "price_str": "860 JPY 〜 1,960 JPY",
                        "min_price": 860,
                        "min_price_str": "860 JPY",
                        "max_price": 1960,
                        "max_price_str": "1,960 JPY"
                    }, {
                        "id": 19,
                        "label": "yamato_anonymous_box_80",
                        "name": "あんしんBOOTHパック 宅急便80サイズ",
                        "short_name": "宅急便80サイズ",
                        "anshin_booth_pack": True,
                        "price_str": "1,080 JPY 〜 2,510 JPY",
                        "min_price": 1080,
                        "min_price_str": "1,080 JPY",
                        "max_price": 2510,
                        "max_price_str": "2,510 JPY"
                    }, {
                        "id": 20,
                        "label": "yamato_anonymous_box_100",
                        "name": "あんしんBOOTHパック 宅急便100サイズ",
                        "short_name": "宅急便100サイズ",
                        "anshin_booth_pack": True,
                        "price_str": "1,320 JPY 〜 3,080 JPY",
                        "min_price": 1320,
                        "min_price_str": "1,320 JPY",
                        "max_price": 3080,
                        "max_price_str": "3,080 JPY"
                    }, {
                        "id": 21,
                        "label": "yamato_anonymous_box_120",
                        "name": "あんしんBOOTHパック 宅急便120サイズ",
                        "short_name": "宅急便120サイズ",
                        "anshin_booth_pack": True,
                        "price_str": "1,540 JPY 〜 3,630 JPY",
                        "min_price": 1540,
                        "min_price_str": "1,540 JPY",
                        "max_price": 3630,
                        "max_price_str": "3,630 JPY"
                    }, {
                        "id": 22,
                        "label": "yamato_anonymous_box_140",
                        "name": "あんしんBOOTHパック 宅急便140サイズ",
                        "short_name": "宅急便140サイズ",
                        "anshin_booth_pack": True,
                        "price_str": "1,790 JPY 〜 4,210 JPY",
                        "min_price": 1790,
                        "min_price_str": "1,790 JPY",
                        "max_price": 4210,
                        "max_price_str": "4,210 JPY"
                    }, {
                        "id": 23,
                        "label": "yamato_anonymous_box_160",
                        "name": "あんしんBOOTHパック 宅急便160サイズ",
                        "short_name": "宅急便160サイズ",
                        "anshin_booth_pack": True,
                        "price_str": "2,010 JPY 〜 4,760 JPY",
                        "min_price": 2010,
                        "min_price_str": "2,010 JPY",
                        "max_price": 4760,
                        "max_price_str": "4,760 JPY"
                    }, {
                        "id": 26,
                        "label": "yamato_anonymous_box_180",
                        "name": "あんしんBOOTHパック 宅急便180サイズ",
                        "short_name": "宅急便180サイズ",
                        "anshin_booth_pack": True,
                        "price_str": "2,340 JPY 〜 5,310 JPY",
                        "min_price": 2340,
                        "min_price_str": "2,340 JPY",
                        "max_price": 5310,
                        "max_price_str": "5,310 JPY"
                    }, {
                        "id": 27,
                        "label": "yamato_anonymous_box_200",
                        "name": "あんしんBOOTHパック 宅急便200サイズ",
                        "short_name": "宅急便200サイズ",
                        "anshin_booth_pack": True,
                        "price_str": "2,780 JPY 〜 5,860 JPY",
                        "min_price": 2780,
                        "min_price_str": "2,780 JPY",
                        "max_price": 5860,
                        "max_price_str": "5,860 JPY"
                    }
                ],
                "shop": {
                    "name": "kragoe",
                    "open": False
                },
                "disk_usage": 1203,
                "disk_quota": 10737418240,
                "max_file_size": 1073741824,
                "shop_has_seller_address": False,
                "shop_has_seller_address_not_japanese": False,
                "sellable_only_in_event": False,
                "variations": [
                    # {
                    #     "id": 11473212,
                    #     "name": "default",
                    #     "type": "digital",
                    #     "stock": 1,
                    #     "price": 114514,
                    #     "margin": None,
                    #     "production_cost": None,
                    #     "item_id": 6825688,
                    #     "display_order": 0,
                    #     "mailbin_enabled": None,
                    #     "tying_musics": True,
                    #     "factory_item_group_id": None,
                    #     "factory_book_id": None,
                    #     "created_at": "2025-04-20T19:33:25.000+09:00",
                    #     "updated_at": "2025-04-20T19:33:25.000+09:00",
                    #     "allocatable_stock": 1,
                    #     "downloadable_ids": [
                    #         # 6546252 下载
                    #     ],
                    #     "min_margin": 0,
                    #     "use_mailbin?": False,
                    #     "waiting_on_arrival?": False,
                    #     "key": "11473212"
                    # }
                ],
                "tracks": [],
                "images": [
                    # self._uploadImgResource(payload.getFiles()[0], itemId)
                ],
                "shop_has_secret_pass": False,
                "has_secret_pass": False,
                "secret_pass": {
                    "question": None,
                    "answer": None
                },
                "shop_has_sale_period": False,
                "has_sale_period": False,
                "sale_period": {
                    "start_at": None,
                    "end_at": None
                },
                "shop_has_storage_upgrade": False,
                "state_event": "publish"
            }
        }
        files = payload.getFiles()
        for index in range(len(files) - 1):
            uir = self._uploadImgResource(files[index], itemId)
            itemDc["item"]["images"].append(uir)

        resultFilesInfos: List[dict] = []
        for file in payload.getFiles():
            downloadableResource = self._uploadDownloadableResource(file, itemId)
            resultFilesInfos = downloadableResource.get("files")
        if not resultFilesInfos:
            log.error(f"booth的下载工作文件downloadables为空")
        itemDc["item"]["downloadables"] = resultFilesInfos

        da = itemDc["item"]["downloadables"]
        log.info(f"[*] uploadFiles: {da}")

        ids: List[int] = []
        for resultFilesInfo in resultFilesInfos:
            _id = resultFilesInfo.get("id")
            if _id:
                ids.append(_id)
            else:
                log.error(f"Failed to downloadableFile id:{resultFilesInfo}")

        dc = itemDc["item"]["variations"]  # self._createItemVariations(itemId, payload)
        dc.append(self._createItemVariations(itemId, payload, ids))

        return itemDc, ids

    def _updateItem(self) -> int:
        result = self._session.request("POST", "https://manage.booth.pm/items?item_form%5Bvariation_type%5D=digital")
        match = re.search(r"/items/(\d+)/edit", result.url)
        if match:
            # 如果找到，提取第一个捕获组 (group 1) 的内容
            item_id = match.group(1)
            log.info(f"提取到的 ID: {item_id}")
            return int(item_id)
        else:
            log.info("在 URL 中未找到匹配的 ID 模式。")
            return 0

    def startUpload(self, payload: BoothPostInfo) -> str:
        itemId = self._updateItem()
        itemBody, downloadableFileIds = self._getItemUpdatePayload(itemId, 695593, payload)
        successPatch = self._makeAPIRequest("PATCH", self._makeItemUpdateURL(itemId), itemBody, None, "init_post.")
        if not successPatch:
            log.error("Failed to update item details. Aborting further steps.")
            return ""

        successPost = self._makeAPIRequest(
            "POST",
            self._makeVariationsURL(itemId),
            self._createItemVariations(itemId, payload, downloadableFileIds),
            None,
            "variations."
        )
        if not successPost:
            log.error("Failed to update item variations.")
        else:
            log.info("Item variations updated successfully (if applicable).")

        log.info("Script finished.")
        finalURL = f"{BASE_URL_SHOP}/items/{itemId}"
        return finalURL

    # if __name__ == "__main__":
    AUTHENTICITY_TOKEN = "cIJD25fwsLn-0wBLErv36U1DNUu4TEnnHIVHmnkJy9QgtSX_MnS5K5pJqJCK2X5dCZu14dUAakuXAmXWuWsKsA"

    CSRF_TOKEN = "cIJD25fwsLn-0wBLErv36U1DNUu4TEnnHIVHmnkJy9QgtSX_MnS5K5pJqJCK2X5dCZu14dUAakuXAmXWuWsKsA"
    COOKIE_STRING = """recent_items=6821619%2C6821729%2C5966423%2C5908939%2C5546825%2C6440258%2C5536474%2C6593883%2C6464123%2C6352844%2C6235947%2C6151314; __cf_bm=cDCcUYwZ80m9zJQYHpRF811Ld87BlHjc_BpzhhF4zPU-1745224607-1.0.1.1-eiA4oQqm4aeY5JBaPHiT9dheL3A3Yb3W6mAujNlqUurWpGws04S1fl7t1fIbffzgaqxe.3Quz3A5h46HLny4EMKhqhM5msP_smmG2LN74rU; cf_clearance=CYxev8gLeza5V7ttZP5n9QyEWfnsESpc.XmgJ4HlXyc-1745224613-1.2.1.1-jZyVp2p7rP_6IsCmT.09OhgxDa4BdKUcEy_InQlCGZ2phvfK2cfZeba0IQ3EVjaVVZMGNLyD7I10_oe.mkEsoXPUFppJMeUpK2VgdNfjJeywN57SLMxi3v9AJgAjJWBbgTYkvCpQt2U3nrDjGa4D1claxMoHqMPAhX3uliZsmoSYGELrLW6gwZcqwbO3PlnnSTPkq1OVpx3T0_5USn8d4Wys0lLa1N4Dwcg99CzNFWyIQhrrjMkOkdTJ8LoAMqGZjELeD5uuhC7_AJVIpkUumm95S3VckYbjHTc0Yo8Km3wVRCvSW2aGbCtmrr80LpLnIoOL43y049VAjvtHGc5T8QnTTovmo7KoNa4YmEM3Ka0; _plaza_session_nktz7u=k2ljw4SgAL1DbvwVJc1EFkn%2FXJFciD2K4run9RIGKYv2%2BTqGKjuKvg8vob7vKLLxugY3%2FFOvBtwPVxRuXqgu0uMI5AetPB3GP2X1h5nN%2Bn2PLkBpK7hrTWtQREVqW%2BQmjdwXJvEkUesNwxr3vQTe%2Bn2qvRsUMgy0IOm8zZpr152H2WQrGMCGRG51HKvU6yFdDWbmmIc6FW%2FOHrwKZcmwhVMsJeFXuHBYtbz8nnJRCFv1uYnLBzJapxvnMHdqVjG4NAXgi4RfxIjIcPKPwKCXEC47IxL48LAhlZYZhUwEnvpbTIr54nE8wDQ0V8AkHoRc72oarMEPOjtUnSFAHfn2NY%2B%2B9n2Gjo2GB0biqGRIxvhSFeUbGRsLtYHGSWVBf5BrPjfM2QFi0bCh%2FORoP7EjE2td%2BTBBhnIeEmg%2Bor6RXChpozTAfpzME1oJsWcWTROUek0AAykEmC7EtteUSqjBUv7SCBo%2BOGXysbGIoUZI4s8Ed3%2FFqiEtNFR4nY%2BDARqvAsJRnVLNUn9XcsHp%2FQSsC26LE1rl5XnqZ%2BmFXHey%2FgaGHAkPCl2%2F%2FUArQMw6c%2FC2ZVrRbNE4zIlJSnYBBFD2ICvJ2YFzKr2oSa90LAmg8%2F8P%2BGdusc8n%2Fz2DleZE1yqVsmrw7XVVl%2FZkbVs4p8ygEyolWGoHTtjvc3a20oDY7sX4n6DlhAIXZzsb9%2FDcFaMsy7M0MkJQ6lB86LyYLurt0vkV47eL0lIAprGE0MlxNORtRtXLyhXgkxLzrcRCe7ypcg1Hu60RMFkyUg1mkpYyJVA0vgwYEN4iqLYRzEVmGhGzCXkgSSisU5YHNsLCKnbhyUTvJABm6MkEa7CrmjArygbmfCHYGwlTgpfHeeeWAst9k0vnLx6r%2Fba8qxB0tt7RLFg5aLa3EftCTlDPB9qd5gyTB1UpaExPygVvTkffb1XP2cF9D8Yfvy6siSDmdqWLTfQNoWTMyoxMnut%2Fxhj0--%2FU7vVls5h7vnxrMy--QZ%2BCZtJiUC4X71BLPXivuQ%3D%3D"""
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"

#     boothUploader = BoothUploader(CSRF_TOKEN, COOKIE_STRING, USER_AGENT, AUTHENTICITY_TOKEN)
#
#     pl = BoothPostInfo()
#     pl.name = "测试name"
#     pl.price = 654321
#     pl.stock = 980
#     pl.tagsArray = ["testTag"]
#     pl.adult = True
#     pl.description = "描述内容。。。。。"
#     pl.append(".\\screeb.png")
#     pl.append(".\\Screenshot 2025-04-21 203248.png")
#
#     boothUploader.startUpload(pl)
