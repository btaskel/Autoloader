import os
import random
import time
import traceback
import uuid
from typing import List

import requests

from src import log
from src.config import config
from src.uploader.payloadbase import PayloadBase


class PixivPostInfo(PayloadBase):
    """保持不变，用于封装 Pixiv 上传所需的信息"""

    def __init__(self):
        super().__init__()
        self.title: str = ""
        self.titleEN: str = ""
        self.caption: str = ""
        self.captionEN: str = ""
        self.adult: bool = False
        self.allowTagEdit: bool = False
        self.tagsArray: List[str] = []


class PixivUploader:
    def __init__(self, csrfToken: str, cookieString: str, userAgent: str):
        """保持初始化接口不变"""
        self.csrfToken: str = csrfToken
        self.cookieString: str = cookieString
        self.userAgent: str = userAgent
        # 将代理配置移到实例变量，以便在方法中使用
        self.proxies = {
            "http": config.http_proxy,
            "https": config.http_proxy,
        }

    @staticmethod
    def _keepAlive(task_func, max_retries=50, base_delay=1, max_delay=64):
        """重试逻辑，使用 log 记录错误并打印 traceback"""
        retries = 0
        delay = base_delay

        while retries < max_retries:
            try:
                return task_func()
            except Exception:
                # 使用 log 记录错误，并直接打印 traceback
                log.error("出现错误:\n>>>>>")
                traceback.print_exc()
                log.error("<<<<<")
                retries += 1
                # 指数增长
                if retries > 5:
                    delay = min(delay * 2, max_delay)
                else:
                    delay = min(delay, max_delay)  # 确保不超过最大值
                # 增加随机抖动
                delay += random.uniform(0, delay / 3)
                time.sleep(delay)

        log.error(f"[保活] 重试次数用尽 ({max_retries}), 退出.")
        # 可以考虑抛出异常或返回特定值表示失败
        # raise RuntimeError(f"Task failed after {max_retries} retries.")
        return None  # 或者返回 None 表示失败

    def startUpload(self, ppi: PixivPostInfo) -> str:
        """
        执行 Pixiv 上传流程。
        Args:
            ppi (PixivPostInfo): 包含上传所需信息的对象。
        Returns:
            int: 上传成功返回 illust_id，冷却中返回 2，失败返回 1。
        """
        post_url = "https://www.pixiv.net/ajax/work/create/illustration"
        # 在方法内部生成 sentry_trace
        sentry_trace = f'{uuid.uuid4().hex}-{uuid.uuid4().hex[:16]}-0'  # 使用 '0' 表示不采样

        # 在方法内部构建 headers，使用实例变量
        headers = {
            "authority": "www.pixiv.net",
            "accept": "application/json",
            "accept-language": "en-GB,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,en-US;q=0.6",
            "baggage": "sentry-environment=production,sentry-release=ee80147438af5620fb60719a59dbba99fc3ba8fb,sentry-public_key=ef1dbbb613954e15a50df0190ec0f023,sentry-trace_id=c995c888a6274d2986a078cf2b335936,sentry-sample_rate=0.1,sentry-transaction=%2Fillustration%2Fcreate,sentry-sampled=false",
            "cookie": self.cookieString,  # 使用实例变量
            "dnt": "1",
            "origin": "https://www.pixiv.net",
            "referer": "https://www.pixiv.net/illustration/create",
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Microsoft Edge";v="122"',  # 可以保持硬编码或从配置读取
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',  # 可以保持硬编码或从配置读取
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "sentry-trace": sentry_trace,  # 使用生成的 trace
            "user-agent": self.userAgent,  # 使用实例变量
            "x-csrf-token": self.csrfToken,  # 使用实例变量
        }

        # --- 嵌套辅助函数 ---
        def generate_image_order(files, payload):
            """生成图片顺序信息并插入 payload (逻辑与示例一致)"""
            image_order = {}
            for index, file_data in enumerate(files):
                # file_data 现在是 ('files[]', (filename, file_object, mimetype))
                # 我们只需要索引
                key = f"imageOrder[{index}][fileKey]"
                file_key = str(index)
                image_order[key] = file_key

                key = f"imageOrder[{index}][type]"
                file_type = "newFile"
                image_order[key] = file_type

            caption_index = None
            payload_keys = list(payload.keys())  # 预先获取键列表以查找索引
            try:
                caption_index = payload_keys.index("captionTranslations[en]")
            except ValueError:
                caption_index = None  # 未找到

            if caption_index is not None:
                # 使用字典推导或更新来合并，更清晰
                new_payload = {}
                items = list(payload.items())
                new_payload.update(items[:caption_index + 1])
                new_payload.update(image_order.items())
                new_payload.update(items[caption_index + 1:])
                payload = new_payload
            else:
                payload.update(image_order)

            return payload

        def generate_files_list(file_paths):
            """准备适用于 requests 的 files 列表 (逻辑与示例一致)"""
            files_list = []
            for file_path in file_paths:
                if not os.path.exists(file_path):
                    log.error(f"文件不存在，跳过: {file_path}")
                    continue  # 跳过不存在的文件

                file_name = os.path.basename(file_path)
                # 简单的 MIME 类型猜测
                file_ext = os.path.splitext(file_name)[1].lower()
                if file_ext in [".png"]:
                    file_format = "image/png"
                elif file_ext in [".jpg", ".jpeg"]:
                    file_format = "image/jpeg"
                elif file_ext in [".gif"]:
                    file_format = "image/gif"
                else:
                    # 对于未知类型，使用通用二进制流类型
                    log.warn(f"未知文件类型 '{file_ext}'，使用 'application/octet-stream'")
                    file_format = "application/octet-stream"  # 更通用的类型

                try:
                    # 确保文件以二进制模式打开
                    file_obj = open(file_path, "rb")
                    files_list.append(("files[]", (file_name, file_obj, file_format)))
                except IOError as e:
                    log.error(f"无法打开文件 {file_path}: {e}")
                    # 确保即使出错，之前打开的文件也能被关闭（虽然 requests 通常会处理）
                    # 在这里可以考虑更健壮的文件处理，例如使用 with 语句管理文件对象列表
                    # 但 requests 的 files 参数接受文件对象，它会在请求后关闭它们

            return files_list

        # --- 结束嵌套辅助函数 ---

        # 使用 ppi 对象获取文件路径
        files_to_upload = generate_files_list(ppi.getFiles())

        # 如果没有有效文件，则无法上传
        if not files_to_upload:
            log.error("没有有效的文件可供上传。")
            # 需要关闭 generate_files_list 中打开的文件对象
            # （如果 generate_files_list 返回了文件对象的话）
            # 在当前实现中，requests 会处理关闭
            return ""

        # 构建 payload，使用 ppi 对象的属性
        payload = {
            "aiType": "notAiGenerated",  # aiGenerated or notAiGenerated
            "allowComment": "true",  # 假设总是允许评论，或从 ppi 获取
            "allowTagEdit": "true" if ppi.allowTagEdit else "false",
            "attributes[bl]": "false",  # 假设默认值，或从 ppi 获取
            "attributes[furry]": "false",  # 假设默认值，或从 ppi 获取
            "attributes[lo]": "false",  # 假设默认值，或从 ppi 获取
            "attributes[yuri]": "false",  # 假设默认值，或从 ppi 获取
            "caption": ppi.caption,
            "captionTranslations[en]": ppi.captionEN,
            "original": "true",  # 假设总是原创，或从 ppi 获取
            "ratings[antisocial]": "false",  # 假设默认值
            "ratings[drug]": "false",  # 假设默认值
            "ratings[religion]": "false",  # 假设默认值
            "ratings[thoughts]": "false",  # 假设默认值
            "ratings[violent]": "false",  # 假设默认值
            "responseAutoAccept": "false",  # 假设默认值
            "restrict": "public",  # 假设总是公开，或从 ppi 获取
            "suggestedTags[]": ["女の子"],  # 固定建议标签，或从 ppi/config 获取
            "tags[]": ppi.tagsArray,
            "title": ppi.title,
            "titleTranslations[en]": ppi.titleEN,
            "xRestrict": "r18",  # 默认 R18
        }

        # 应用图片顺序
        payload = generate_image_order(files_to_upload, payload)

        # 根据 ppi.adult 调整 R18 设置
        if not ppi.adult:
            payload["xRestrict"] = "general"
            payload["sexual"] = "false"  # 全年龄需要明确设置 sexual 为 false

        post_response = None
        try:
            # 使用 self._keepAlive 执行 POST 请求
            post_response_raw = self._keepAlive(
                lambda: requests.request(
                    "POST",
                    post_url,
                    headers=headers,
                    data=payload,
                    files=files_to_upload,  # 传递准备好的文件列表
                    proxies=self.proxies  # 使用实例的代理设置
                )
            )

            # 检查 keepAlive 是否返回 None (表示重试失败)
            if post_response_raw is None:
                log.error("POST 请求在多次重试后失败。")
                return ""

            # 尝试解析 JSON
            try:
                post_response = post_response_raw.json()
            except requests.exceptions.JSONDecodeError:
                log.error(f"POST 响应不是有效的 JSON: {post_response_raw.text}")
                return ""

            # 检查 Pixiv 返回的错误标志
            if not post_response.get("error", True):  # Pixiv 成功时 error=False
                # POST 成功，查询进度
                convert_key = post_response.get("body", {}).get("convertKey")
                if not convert_key:
                    log.error(f"POST 成功但未找到 convertKey: {post_response}")
                    return ""

                get_url = f"https://www.pixiv.net/ajax/work/create/illustration/progress?convertKey={convert_key}&lang=zh"
                illust_id = None
                while not illust_id:
                    status_resp_raw = self._keepAlive(
                        lambda: requests.request("GET", get_url, headers=headers, data={}, proxies=self.proxies)
                    )

                    if status_resp_raw is None:
                        log.error("GET 状态请求在多次重试后失败。")
                        return ""

                    try:
                        status_resp = status_resp_raw.json()
                    except requests.exceptions.JSONDecodeError:
                        log.error(f"GET 状态响应不是有效的 JSON: {status_resp_raw.text}")
                        # 即使状态查询失败，之前的 POST 可能已成功，但不确定 illust_id
                        return ""

                    status_body = status_resp.get("body", {})
                    if not status_resp.get("error") and status_body.get("status") == "COMPLETE":
                        illust_id = status_body.get("illustId")
                        if not illust_id:
                            log.error(f"状态为 COMPLETE 但未找到 illustId: {status_resp}")
                            return ""
                    elif status_resp.get("error"):
                        log.error(f"GET 状态查询返回错误: {status_resp.get('message', status_resp_raw.text)}")
                        return ""
                    else:
                        # 状态不是 COMPLETE，等待后重试
                        time.sleep(1)

                # 成功获取 illust_id
                time.sleep(1)  # 短暂等待确保处理完成
                log.info(f"上传成功, PID: {illust_id}")
                return f"https://www.pixiv.net/artworks/{illust_id}"
            else:
                # POST 请求返回错误
                error_body = post_response.get("body", {})
                if error_body.get("errors", {}).get("gRecaptchaResponse"):
                    log.warn("上传暂停: 投稿冷却中 (触发 reCAPTCHA)")
                    return ""
                else:
                    error_message = post_response.get('message', post_response_raw.text)
                    log.error(f"上传失败: {error_message}")
                    return ""
        finally:
            # 确保关闭所有打开的文件对象
            for _, file_tuple in files_to_upload:
                # file_tuple is (filename, file_object, mimetype)
                try:
                    file_tuple[1].close()
                except Exception as e:
                    log.warn(f"关闭文件 {file_tuple[0]} 时出错: {e}")
            return ""
