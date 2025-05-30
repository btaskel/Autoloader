import os
from typing import List, Optional

from src import log
from src.config import config
from src.aigc.tag_parser import parseImgTags, TagAnalysisResult
from src.mode_parser.upload_block import Order
from src.uploader.payloadbase import allowWebsite
from src.uploader.uploader_booth import BoothPostInfo
from src.uploader.uploader_dropbox import DropboxUploader, DropboxPayload
from src.uploader.uploader_pixiv import PixivPostInfo, PixivUploader
from src.uploader.uploader_unifans import UnifansUploader, UnifansPostInfo
from src.utils.fileio import getDateTimeSuffixPath, createFile, compressFilesToZip

class CaptionInfo:
    """
    %url%: 上一个upload块的URL
    %number%: 当前upload块生成的图片数量
    %all_number%: 总共生成的图片数量
    """
    url: str = ""
    number: int = 0
    all_number: int = 0


def parseCaption(caption: str, ci: CaptionInfo) -> str:
    captionInfoDc = vars(ci)
    for k, v in captionInfoDc.items():
        keyword = f"%{k}%"
        if keyword in caption:
            if v:
                log.info(f"将caption: {keyword}替换为{str(v)}")
                caption = caption.replace(keyword, str(v))
            else:
                log.warn(f"caption: {keyword}替换失败: {caption}")
    return caption

class Uploader:
    def __init__(self):
        self.historyOrder: List[Order] = []
        self.allOrderNumber: int = 0

    def _replaceKeyword(self, order: Order, text: str) -> str:
        ci = CaptionInfo()
        previousUrl = ""
        if self.historyOrder:  # 检查历史记录是否为空
            lastCompletedOrder = self.historyOrder[-1]  # 获取最后一个完成的 order
            previousUrl = lastCompletedOrder.dstURL if lastCompletedOrder.dstURL else ""  # 获取其 URL
        ci.url = previousUrl

        ci.number = order.len()
        # self.allOrderNumber 在这里获取的是处理当前 order *之前* 的总数
        ci.allNumber = self.allOrderNumber
        caption = parseCaption(text, ci)
        order.ui.debug(f"处理后的 keyword: {caption}")
        return caption

    def _parseCaption(self, order: Order) -> str:
        if order.ui.targetCaption:
            return self._replaceKeyword(order, order.ui.targetCaption)
        return ""

    def _parseExtensionFileContext(self, order: Order) -> str:
        if order.ui.targetExtensionFileContext:
            return self._replaceKeyword(order, order.ui.targetExtensionFileContext)
        return ""

    @staticmethod
    def _check(order: Order):
        activeFiles = order.sortByActive()
        if len(activeFiles):
            order.ui.error(f"执行结果没有输出的文件路径，因此无法上传到:{order.ui.targetWebsiteName}")
            return

        website = allowWebsite.get(order.ui.targetWebsiteName)
        if not website:
            order.ui.error(f"不支持的网站上传:{order.ui.targetWebsiteName}")
            return

        if order.ui.targetPackerEnable > website.packerEnable:
            order.ui.error(f"当前网站{website}不支持压缩上传!正在尝试使用单独文件上传")
            return

    def append(self, order: Order):
        self._check(order)

        # 进行洗牌
        tagAnalysisResult: Optional[TagAnalysisResult] = None
        while True:
            try:
                tagAnalysisResult = parseImgTags(order)
                break
            except Exception as e:
                order.ui.warn(f"tag分析失败: {e}")
                ok = input("遇到意外失败,是否重试(y/n):").lower()
                if ok == "y" or ok == "yes":
                    continue
                else:
                    return

        keepTags = [tagAnalysisResult.source, tagAnalysisResult.character]

        # 处理描述
        caption = self._parseCaption(order)

        files = order.paths().copy()

        # 拓展文件上传
        extensionFileContext = self._parseExtensionFileContext(order)
        if extensionFileContext:
            extensionFileContextPath = os.path.join(config.output_path, "download_link.txt")
            createFile(extensionFileContextPath, extensionFileContext)
            files.append(extensionFileContextPath)

        # 如果启用了压缩上传
        if order.ui.targetPackerEnable:
            zipFilePath = compressFilesToZip(files[order.ui.targetPackerStartPos:],
                                             os.path.join(config.output_path, "download_link.zip"))
            if not zipFilePath:
                order.ui.fatal("上传文件压缩失败")
            files = files[:order.ui.targetPackerStartPos]
            files.append(zipFilePath)

        dstURL: str = ""
        title = f"{tagAnalysisResult.source} {tagAnalysisResult.character}"

        def cutTags(_tags: List[str], _keepTags: List[str], _paddingNum: int) -> List[str]:
            _extNum = len(config.last_tags) + len(_keepTags) + len(config.front_tags)
            availableVariableSpace = _paddingNum - _extNum

            if availableVariableSpace < 0:
                availableVariableSpace = 0

            _tags = _tags[:availableVariableSpace]
            if config.front_tags:
                var = config.front_tags.copy()
                var.extend(_tags)
                _tags = var

            _tags.extend(_keepTags)

            if config.last_tags:
                _tags.extend(config.last_tags)
            return _tags

        # 上传
        match order.ui.targetWebsiteName.lower():
            case "pixiv":
                tagAnalysisResult.other = cutTags(tagAnalysisResult.other, keepTags, 10)  # tag最长为10
                uploader = PixivUploader(
                    config.pixiv_csrf_token,
                    config.pixiv_cookie,
                    config.user_agent
                )
                ppi = PixivPostInfo()

                ppi.title = title
                if caption:
                    order.ui.debug(f"使用order携带的caption作为描述")
                    ppi.caption = caption
                else:
                    order.ui.debug(f"使用tagger的处理结果作为caption描述")
                    ppi.caption = tagAnalysisResult.toStr()
                ppi.tagsArray = tagAnalysisResult.append()
                ppi.adult = order.ui.sfwLevelNum < 2
                ppi.allowTagEdit = True
                ppi.extend(files)
                order.dstURL = uploader.startUpload(ppi)
            case "booth":
                from src.uploader.uploader_booth import BoothUploader
                tagAnalysisResult.other = cutTags(tagAnalysisResult.other, keepTags, 8)
                uploader = BoothUploader(
                    config.booth_csrf_token,
                    config.booth_cookie,
                    config.user_agent,
                    config.booth_authenticity_token
                )
                bpi = BoothPostInfo()
                bpi.name = f"{tagAnalysisResult.source} {tagAnalysisResult.character}"
                if caption:
                    order.ui.debug(f"使用order携带的caption作为描述")
                    bpi.caption = caption
                    bpi.description = caption
                else:
                    order.ui.debug(f"使用tagger的处理结果作为caption描述")
                    bpi.caption = tagAnalysisResult.toStr()
                    bpi.description = tagAnalysisResult.toStr()
                bpi.tagsArray = tagAnalysisResult.append()
                bpi.adult = order.ui.sfwLevelNum < 2
                bpi.stock = 999
                bpi.price = 400
                bpi.extend(files)
                order.dstURL = uploader.startUpload(bpi)

            case "dropbox":
                uploader = DropboxUploader(
                    config.dropbox_access_token
                )
                dpi = DropboxPayload()
                dpi.shareEnable = True
                dpi.folderName = getDateTimeSuffixPath(title)
                dpi.extend(files)
                order.dstURL = uploader.startUpload(dpi)
            case "unifans":
                uploader = UnifansUploader(
                    config.unifans_auth_token,
                    config.unifans_account_id,
                    config.user_agent
                )
                upi = UnifansPostInfo()
                upi.title = title
                if caption:
                    order.ui.debug(f"使用order携带的caption作为描述")
                    upi.content = caption
                    upi.previewContext = caption
                else:
                    order.ui.debug(f"使用tagger的处理结果作为caption描述")
                    upi.content = tagAnalysisResult.toStr()
                    upi.previewContext = tagAnalysisResult.toStr()
                upi.schemeIds = config.unifans_scheme_ids
                upi.extend(files)
                uploader.startUpload(upi)
            case "test":
                order.ui.info("因为设置了website=test，所以跳过上传操作")
                return
            case _:
                order.ui.fatal(f"无效的上传网站: {order.ui.targetWebsiteName}")

        self.historyOrder.append(order)
        self.allOrderNumber += order.len()
