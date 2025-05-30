import json
import os
from typing import List, Dict

from src import log
from src.config import config
from src.uploader.payloadbase import allowWebsite
from src.utils.fileio import getSuffixPath


class UploadInfo:
    def __init__(self, index: int = 0):
        self.targetWebsiteName: str = ""
        self.targetPackerEnable: bool = False
        self.targetPackerStartPos: int = 0
        self.targetCaption: str = ""
        self.targetExtensionFileContext: str = ""

        self.workflowFixedNodeSeedNames: List[str] = []
        self.workflowUniformString: str = ""
        self.workflowName: str = ""

        self.rmDefaultTags: List[str] = []
        self.addDefaultTags: List[str] = []

        self.number: int = 0
        self.batch: int = 0
        self.safetyCoverSFWLevelNum: int = 0
        self.sfwLevelNum: int = 0
        self.waterMarkEnable: bool = False
        self.mosaicEnable: bool = False

        self._uploadIndex: int = index  # 仅用于日志

    def check(self) -> bool:
        typeCheckDc:Dict[str, list] = {
            "target: website_name": [self.targetWebsiteName, str],
            "target: packer_enable": [self.targetPackerEnable, bool],
            "target: packer_start_pos": [self.targetPackerStartPos, int],
            "target: caption": [self.targetCaption, str],
            "target: extension_file_context": [self.targetExtensionFileContext, str],

            "workflow: fixed_node_seed_names": [self.workflowFixedNodeSeedNames, list],
            "workflow: uniform_string": [self.workflowUniformString, str],
            "workflow: workflow_name": [self.workflowName, str],

            "number": [self.number, int],
            "batch": [self.batch, int],
            "safety_cover_sfw_level_num": [self.safetyCoverSFWLevelNum, int],
            "sfw_level_num": [self.sfwLevelNum, int],
            "watermark_enable": [self.waterMarkEnable, bool],
            "mosaic_enable": [self.mosaicEnable, bool],

            "remove_default_tags": [self.rmDefaultTags, list],
            "add_default_tags": [self.addDefaultTags, list],
        }
        for k, v in typeCheckDc.items():
            if not isinstance(v[0], v[1]):
                self.error(f"{k}字段类型错误:{type(v[0])} 实际应该为: {type(v[1])}")
                return False

        if self.targetWebsiteName not in allowWebsite:
            self.error(f"要上传的网站不支持:{self.targetWebsiteName}")
            return False

        if self.targetPackerEnable and self.number < self.targetPackerStartPos:
            self.error(f"因为number < PackerStartPos 因此无法进行打包")
            return False

        if self.number <= 0:
            self.error(f"number生成的数量不能小于0:{self.number}")
            return False

        if self.batch < 0:
            self.error(f"batch批次数量不能小于0:{self.batch}")
            return False
        return True

    def fatal(self, msg, *args, **kwargs):
        log.fatal(f"uploads[{self._uploadIndex}]: {msg}", *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        log.error(f"uploads[{self._uploadIndex}]: {msg}", *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        log.warn(f"uploads[{self._uploadIndex}]: {msg}", *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        log.info(f"uploads[{self._uploadIndex}]: {msg}", *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        log.debug(f"uploads[{self._uploadIndex}]: {msg}", *args, **kwargs)


class Image:
    def __init__(self):
        self._index: int = 0
        self.outputPath: str = ""
        self.sfwLevelNum: int = 0
        self.workflowName: str = ""
        self.mosaicEnable: bool = False
        self.mosaicFin: bool = False
        self.watermarkEnable: bool = False
        self.watermarkFin: bool = False

    def setIndex(self, index: int):
        self._index = index

    def getIndex(self) -> int:
        return self._index


class Order:
    def __init__(self, ui: UploadInfo):
        # self._imagePointer: int = 0
        self._images: List[Image] = []
        self._mode: str = ""

        self.taskInfo = {}
        self.dstURL: str = ""
        self.extensionFileContextPath: str = ""

        self.ui = ui
        self._init()

    def _init(self):
        self._addImage()

    def _addImage(self):
        for i in range(self.ui.number):
            image = Image()
            image.setIndex(i)
            self._setSfwLevelNum(image, i)
            image.mosaicEnable = self.ui.mosaicEnable
            image.watermarkEnable = self.ui.waterMarkEnable

            if self.ui.workflowName:
                image.workflowName = self.ui.workflowName
            else:
                image.workflowName = self._marchSFWLevel(image.sfwLevelNum)

            self._images.append(image)

    def _setSfwLevelNum(self, image: Image, index: int):
        if index:
            image.sfwLevelNum = self.ui.sfwLevelNum
            return
        image.sfwLevelNum = self.ui.safetyCoverSFWLevelNum

    def _marchSFWLevel(self, sfwLevelNum: int) -> str:
        def __marchSFWLevel(workflowName: str) -> str:
            if os.path.exists(os.path.join(config.workflow_path, workflowName)):
                self.ui.debug(f"预生成图片对象匹配到可用的{workflowName}")
                return workflowName
            self.ui.error(f"预生成图片对象没有匹配到任何可用的workflow:{workflowName}")
            return ""

        match sfwLevelNum:
            case 0:
                return __marchSFWLevel(config.workflow_name_nsfw_name)
            case 1:
                return __marchSFWLevel(config.workflow_name_nsfw_censored_name)
            case 2:
                return __marchSFWLevel(config.workflow_name_sfw_name)
            case _:
                self.ui.error("预生成图片对象sfw等级不能 >2 或 <0")
        return ""

    def getImages(self) -> List[Image]:
        return self._images

    def sort(self) -> List[Image]:
        ls: List[Image | None] = [None] * len(self._images)
        for image in self._images:
            ls[image.getIndex()] = image
        return ls

    def sortByActive(self) -> List[Image]:
        ls = []
        self.sort()
        for image in self._images:
            if not image.outputPath:
                ls.append(image)
                continue
            if image.mosaicEnable != image.mosaicFin:
                ls.append(image)
                continue
            if image.watermarkEnable != image.watermarkFin:
                ls.append(image)
                continue
        return ls

    def select(self, s: int, e: int) -> List[Image]:
        return self._images[s:e]

    def len(self) -> int:
        return len(self._images)

    def paths(self) -> List[str]:
        ls = []
        self.sort()
        for image in self._images:
            ls.append(image.outputPath)
        return ls

    def saveOrder(self):
        save_filename = getSuffixPath("image_order.json")  # 使用不同的基础文件名区分
        old_order_folder_path = os.path.join(config.order_path, "old")
        if not os.path.exists(old_order_folder_path):
            try:
                os.makedirs(old_order_folder_path, exist_ok=True)
            except OSError as e:
                # 使用 ui 对象的 logger 记录错误
                self.ui.error(f"创建旧order目录失败: {old_order_folder_path}, 错误: {e}")
                return  # 无法创建目录，保存失败

        save_path = os.path.join(old_order_folder_path, save_filename)

        # 2. 准备要保存的数据字典
        data_to_save = {
            # 保存 UploadInfo 的所有属性
            "ui": vars(self.ui).copy(),
            # 保存每个 Image 对象的状态
            # 使用列表推导式将每个 Image 对象转换为字典
            "_images": [vars(img).copy() for img in self._images],
            # 保存 taskInfo
            "taskInfo": self.taskInfo,
            # 保存目标 URL
            "dstURL": self.dstURL
        }
        # 移除 UploadInfo 中不可序列化的 _uploadIndex (虽然 vars() 通常不包含私有成员，但以防万一)
        # 或者确保 UploadInfo 的 __dict__ 不包含非序列化内容
        # 在这个例子中，vars(self.ui) 应该没问题，因为 _uploadIndex 是基本类型

        # 3. 写入 JSON 文件
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                # indent=4 使 JSON 文件更易读
                # ensure_ascii=False 允许非 ASCII 字符（例如中文标题/标签）
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            # 使用 ui 对象的 logger 记录成功信息
            self.ui.info(f"ImageOrder 自动保存成功: {save_path}")
        except TypeError as e:
            self.ui.error(f"保存 ImageOrder 失败：数据无法序列化为 JSON。错误: {e}")
            # 可以考虑打印 data_to_save 的部分内容帮助调试
            log.debug(f"无法序列化的数据（部分）: {str(data_to_save)[:500]}")  # 打印前500字符
        except IOError as e:
            self.ui.error(f"保存 ImageOrder 失败：写入文件时发生 IO 错误。路径: {save_path}, 错误: {e}")
        except Exception as e:
            # 捕获其他意外错误
            self.ui.fatal(f"保存 ImageOrder 时发生未知错误: {e}")


def loadOrders(orderScriptPath: str) -> (List[Order], str):
    orders: List[Order] = []
    try:
        with open(orderScriptPath, mode="r", encoding="utf-8") as f:
            script: dict = json.load(f)
    except FileNotFoundError as e:
        log.fatal(f"无效的项目路径: {e}")

    _uploads: List[dict] = script.get("uploads")
    if not len(_uploads):
        log.error("上传块中没有对象")
    _global: dict = script.get("global")

    uploadInfos: List[UploadInfo] = []
    index: int = 0
    for upload in _uploads:
        ui = UploadInfo(index)
        target: dict = upload.get("target")
        if target:
            ui.targetWebsiteName = target.get("website_name")
            ui.targetPackerEnable = target.get("packer_enable")
            ui.targetPackerStartPos = target.get("packer_start_pos")
            ui.targetCaption = target.get("caption")
            ui.targetExtensionFileContext = target.get("extension_file_context")
        else:
            log.error(f"当前upload块[{index}]缺少target键值对")
            raise KeyError("当前upload块缺少target键值对")

        workflow: dict = upload.get("workflow")
        if workflow:
            ui.workflowName = workflow.get("workflow_name")
            if ui.workflowName:
                log.debug(f"upload块[{index}] 使用的workflow: {ui.workflowName}")
            else:
                log.debug(f"upload块[{index}] 没有携带workflow, 稍后将会使用默认的workflow")
            ui.workflowFixedNodeSeedNames = workflow.get("fixed_node_seed_names")
            ui.workflowUniformString = workflow.get("uniform_string")

        ui.number = upload.get("number")
        ui.batch = upload.get("batch")
        ui.safetyCoverSFWLevelNum = upload.get("safety_cover_sfw_level_num")
        ui.sfwLevelNum = upload.get("sfw_level_num")
        ui.waterMarkEnable = upload.get("watermark_enable")
        ui.mosaicEnable = upload.get("mosaic_enable")
        uploadInfos.append(ui)
        index += 1

    for uploadInfo in uploadInfos:
        if not uploadInfo.check():
            continue

        order: Order = Order(uploadInfo)
        orders.append(order)
    return orders, script.get("mode")


def loadOrderSave(order_save_path: str) -> tuple[Order, str] | tuple[None, str]:
    """
    从 JSON 文件加载 ImageOrder 对象的状态。
    返回加载的 ImageOrder 对象，如果失败则返回 None。
    """
    try:
        with open(order_save_path, "r", encoding="utf-8") as f:
            order_data: dict = json.load(f)
    except FileNotFoundError:
        log.error(f"无法找到order保存文件: {order_save_path}")
        return None, ""
    except json.JSONDecodeError as e:
        log.error(f"解析order保存文件失败: {order_save_path}, 错误: {e}")
        return None, ""
    except Exception as e:
        log.error(f"加载order保存文件时发生未知错误: {order_save_path}, 错误: {e}")
        return None, ""

    try:
        # 1. 恢复 UploadInfo
        ui_data = order_data.get("ui")
        if not isinstance(ui_data, dict):
            log.error("order数据中缺少或无效的 'ui' 部分")
            return None, ""
        # 创建一个临时的 UploadInfo 实例来承载数据
        # 注意：UploadInfo 的 __init__ 需要 index，我们从 ui_data 中获取
        ui_index = ui_data.get("_uploadIndex", -1)  # 提供默认值以防万一
        ui = UploadInfo(ui_index)
        # 将加载的属性更新到 ui 实例中
        # vars(ui).update(ui_data) # 这种方式更简洁
        for key, value in ui_data.items():
            setattr(ui, key, value)  # 或者逐个设置属性

        # 2. 创建 ImageOrder 实例
        # 注意：ImageOrder 的 __init__ 需要一个 UploadInfo 对象
        order = Order(ui)  # 使用恢复的 ui 对象

        # 3. 恢复 Image 列表
        images_data = order_data.get("_images")
        if not isinstance(images_data, list):
            log.error("order数据中缺少或无效的 '_images' 部分")
            # 即使图片列表丢失，也许仍然可以恢复部分状态？取决于需求
            # 这里我们选择失败
            return None, ""

        mode = order_data.get("_mode")
        if not mode:
            log.error("order数据中缺少或无效的 '_mode' 部分")
            return None, ""

        restored_images: List[Image] = []
        for img_data in images_data:
            if not isinstance(img_data, dict):
                log.warn(f"跳过无效的图片数据项: {img_data}")
                continue
            img = Image()
            # vars(img).update(img_data) # 简洁方式
            for key, value in img_data.items():
                setattr(img, key, value)  # 或者逐个设置
            restored_images.append(img)

        # 将恢复的图片列表赋值给 order 对象
        order._images = restored_images

        # 4. 恢复其他属性
        order.taskInfo = order_data.get("taskInfo", {})  # 提供默认空字典
        order.dstURL = order_data.get("dstURL", "")  # 提供默认空字符串

        # 5. （可选）执行检查
        if not order.ui.check():
            order.ui.error("恢复的 ImageOrder 未通过检查，可能存在问题。")
            # 根据需要决定是否返回 None 或继续

        log.info(f"成功从 {order_save_path} 恢复 ImageOrder")
        return order, mode

    except Exception as e:
        log.fatal(f"从数据构建 ImageOrder 对象时出错: {e}")
    return None, ""
