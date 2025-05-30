from PIL import Image

from src import log
from src.config import config
from src.mode_parser.upload_block import Order
from src.utils.detector import detector, detectorYolo, mosaicBlurry, putWatermark


def extraImgPostProcess(order: Order):
    order.ui.info("开始进行马赛克检测")
    activeImages = order.sortByActive()
    for activeImage in activeImages:
        if activeImage.mosaicEnable and not activeImage.mosaicFin:
            _parseMosaicBlurry(activeImage.outputPath)
            activeImage.mosaicFin = True

        if activeImage.watermarkEnable and not activeImage.watermarkFin:
            putWatermark(activeImage.outputPath, config.watermark_path)
            activeImage.watermarkFin = True

def _parseMosaicBlurry(savePath: str) -> str:
    log.debug(f"马赛克检测开始，打开了文件{savePath}")
    with Image.open(savePath) as image:
        try:
            bboxLists = detector(savePath)
            if len(bboxLists) == 0:
                try:
                    bboxLists = detectorYolo(savePath)
                except Exception as e:
                    log.warn(f"使用nudenet和yolo检测失败:{e}")
            mosaicBlurry(savePath, image, bboxLists)
        except Exception as e:
            log.warn(f"使用nudenet检测失败，尝试使用yolo:{e}")
            bboxLists = detectorYolo(savePath)
            mosaicBlurry(savePath, image, bboxLists)
    return savePath