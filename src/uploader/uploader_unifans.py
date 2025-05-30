import os
from typing import Optional, Dict, List

import requests

from src import log
from src.config import config
from src.uploader.payloadbase import PayloadBase

PRIVILEGE = 2  # 2 通常表示对特定scheme可见
WEB_VERSION = "202505191104"  # 从HAR中获取的web版本号

# --- API端点 ---
UPLOAD_URL = "https://upload2.unifans.io/common/uploadAttachment"
PUBLISH_POST_URL = "https://api.unifans.io/creator/publishPost"

MAX_UPLOAD_FILES = 15  # 最大上传文件数


class UnifansPostInfo(PayloadBase):
    def __init__(self):
        super().__init__()
        self.title: str = ""
        self.content: str = ""
        self.previewContext: str = ""
        self.schemeIds: List[str] = []  # 方案ID

    def slice(self) -> List[List[str]]:
        files = self.getFiles()
        if len(files) < 1:
            raise FileNotFoundError("没有任何文件就进行了切片操作")

        if len(files) < MAX_UPLOAD_FILES:
            return [files]

        result: List[List[str]] = []
        for i in range(0, len(files), MAX_UPLOAD_FILES):
            result.append(files[i:i + MAX_UPLOAD_FILES])

        return result


class UnifansUploader:
    def __init__(self, authToken: str, accountId: str, userAgent: str):
        self.authToken = authToken
        self.accountId = accountId
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": userAgent,
            # 与HAR一致
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://app.unifans.io",
            "Referer": "https://app.unifans.io/",
            "Authorization": authToken,  # 直接使用 token，而不是 Bearer token
            # 根据HAR，upload请求的Content-Type由requests库在发送multipart/form-data时自动设置
            # publishPost请求的Content-Type在发送json时由requests库自动设置为application/json
        })
        self.session.proxies = config.proxies

    # --- 辅助函数 ---
    @staticmethod
    def create_post_html_content(text_content: str):
        """简单的将纯文本包装成Unifans编辑器产生的HTML结构"""
        # 基于HAR中的内容，Froala Editor会添加一个推广链接，这里我们简化
        # 您可以根据需要构建更复杂的HTML
        return f'<div style="font-size: 0.875rem;"><p>{text_content}</p></div>'

    def upload_image(self, image_path: str, compress_type: str = "high", include_thumbnail: bool = False) \
            -> Optional[Dict[str, str]]:
        """
        上传图片到Unifans。
        compress_type: "low" 或 "high"
        include_thumbnail: True 或 False (根据HAR，low压缩时有，high压缩时无)
        """
        if not os.path.exists(image_path):
            log.debug(f"错误：图片文件 {image_path} 不存在。")
            return None

        files = {
            'file': (os.path.basename(image_path), open(image_path, 'rb'), 'image/png')  # 假设是PNG，根据实际情况修改
        }
        payload = {
            'accountId': self.accountId,
            'type': 'picture',
            'compressType': compress_type,
        }
        if include_thumbnail:
            payload['thumbnail'] = 'true'

        log.debug(f"正在上传图片 ({compress_type}压缩)...")
        try:
            response = self.session.post(UPLOAD_URL, files=files, data=payload)
            response.raise_for_status()  # 如果请求失败则抛出HTTPError

            upload_data = response.json()
            if upload_data.get("code") == 0 and "data" in upload_data:
                log.debug(f"图片上传成功 ({compress_type}压缩):")
                log.debug(f"  Attachment ID: {upload_data['data']['attachmentId']}")
                log.debug(f"  Address: {upload_data['data']['address']}")
                return upload_data['data']
            else:
                log.error(f"图片上传失败 ({compress_type}压缩): {upload_data.get('message')}")
                log.error(f"完整响应: {upload_data}")
                return None
        except requests.exceptions.RequestException as e:
            log.debug(f"图片上传请求错误 ({compress_type}压缩): {e}")
            if hasattr(e, 'response') and e.response is not None:
                log.debug(f"响应内容: {e.response.text}")
            return None
        finally:
            # 关闭文件对象
            if 'file' in files and files['file'][1]:
                files['file'][1].close()

    def publish_post(self, title: str, content_html: str, attachment_ids, scheme_ids,
                     preview_picture_url: str, preview_text: str):
        """发布帖子"""
        payload = {
            "title": title,
            "postText": content_html,
            "isTranslated": False,
            "defaultLanguage": "zh",  # 根据您的需要调整
            "translatedLanguage": "en",
            "titleTranslate": "",
            "postTextTranslate": "",
            "hashTags": [],  # 如果需要可以添加标签 ["tag1", "tag2"]
            "privilege": PRIVILEGE,
            "attachments": attachment_ids,  # 列表，例如 ["attachment_id_from_upload1"]
            "scheme": scheme_ids,  # 列表，例如 ["your_scheme_id"]
            "singlePostFlag": 0,
            "fixedPrice": False,
            "singlePostAmount": 0.1,  # 根据HAR，如果不是单独售卖的帖子，这个值可能不重要
            "previewPictureFlag": True,
            "previewTextFlag": bool(preview_text),  # 如果有预览文字则为True
            "previewPicture": preview_picture_url,
            "previewText": preview_text,
            "collections": [],
            "webVersion": WEB_VERSION
        }

        log.debug("正在发布帖子...")
        try:
            response = self.session.post(PUBLISH_POST_URL, json=payload)
            response.raise_for_status()

            post_data = response.json()
            if post_data.get("code") == 0:
                log.info(f"帖子发布成功! Post ID: {post_data['data']['postId']}")
                return post_data['data']
            else:
                log.error(f"帖子发布失败: {post_data.get('message')}")
                log.error(f"完整响应: {post_data}")
                return None
        except requests.exceptions.RequestException as e:
            log.error(f"帖子发布请求错误: {e}")
            if hasattr(e, 'response') and e.response is not None:
                log.error(f"响应内容: {e.response.text}")
            return None

    def upload_image_for_content(self, image_paths, compress_type="low", include_thumbnail=True) -> List[
        Dict[str, str]]:
        """
        上传图片用于帖子内容和预览。
        这里假设使用同一张图片进行两次上传，您可以根据需要调整逻辑。
        """
        log.debug(f"正在上传图片用于内容和预览 ({compress_type}压缩)...")

        result: List[Dict[str, str]] = []
        for image_path in image_paths:
            data = self.upload_image(image_path, compress_type, include_thumbnail)
            if data:
                result.append(data)
        return result

    def upload_image_for_preview(self, image_path, compress_type="high", include_thumbnail=False) -> Optional[
        Dict[str, str]]:
        """
        上传图片用于帖子预览。
        这里假设使用同一张图片进行两次上传，您可以根据需要调整逻辑。
        """
        log.debug(f"正在上传图片用于预览 ({compress_type}压缩)...")
        return self.upload_image(image_path, compress_type, include_thumbnail)

    def startUpload(self, payload: UnifansPostInfo):
        fileLists = payload.slice()
        totalPostNum = len(fileLists)
        counter = 1
        for fileList in fileLists:
            contentDatas = self.upload_image_for_content(fileList)
            if not contentDatas:
                log.fatal("用于内容的图片上传失败，脚本终止。")

            attachmentIds = []
            for contentData in contentDatas:
                attachmentIds.append(contentData.get("attachmentId"))

            previewImageData = self.upload_image_for_preview(fileList[0])
            if not previewImageData:
                log.fatal("用于预览的图片上传失败，脚本终止。")

            previewImageURL = previewImageData.get("address")

            content = self.create_post_html_content(payload.content)

            # 步骤3: 发布帖子
            self.publish_post(
                title=payload.title + f" ({counter}/{totalPostNum})",
                content_html=content,
                attachment_ids=attachmentIds,
                scheme_ids=payload.schemeIds,
                preview_picture_url=previewImageURL,
                preview_text=payload.previewContext
            )
            counter += 1


if __name__ == '__main__':
    AUTH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2NvdW50SWQiOiIyNDZiNTMyNTI1YTI2ZGM4ZDZhNzcwYjdmNTVlNmVkZiIsInJvbGUiOjEsImlhdCI6MTc0ODE1NDY2MSwiZXhwIjoxNzQ4NzU5NDYxfQ.qbQp8akQmZTxtlv1vK2LafQeVKFHmi9qd4BbBYf2Fms"
    ACCOUNT_ID = "246b532525a26dc8d6a770b7f55e6edf"
    uploader = UnifansUploader(AUTH_TOKEN, ACCOUNT_ID)
    upi = UnifansPostInfo()
    upi.content = "testContent"
    upi.previewContext = "testPreviewContent"
    upi.title = "testTitle"
    uploader.startUpload(upi)
