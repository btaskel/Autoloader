import json
import os
from typing import List

from PIL import ImageFilter
from PIL.ImageFile import ImageFile
from nudenet import NudeDetector

from src import log
from src.config import config


def detector(imgPath: str) -> List[list]:
    nude_detector = NudeDetector()
    # 这个库不能使用中文文件名
    # tmpPathWithFileName = os.path.join(tmpPath, os.path.basename(imagePath))
    # if os.path.exists(tmpPathWithFileName):
    #     os.remove(tmpPathWithFileName)
    # shutil.copyfile(imagePath, tmpPathWithFileName)
    box_list = []
    body = nude_detector.detect(imgPath)
    for part in body:
        if part["class"] in ["FEMALE_GENITALIA_EXPOSED", "MALE_GENITALIA_EXPOSED"]:
            log.debug("检测到: {}".format(part["class"]))
            x = part["box"][0]
            y = part["box"][1]
            w = part["box"][2]
            h = part["box"][3]
            box_list.append([x, y, w, h])
    log.debug(f"使用nudenet进行检测完成: {imgPath}, boxList: {box_list}")
    return box_list


from ultralytics import YOLO


def detectorYolo(imgPath: str) -> List[list]:
    model = YOLO(config.mosaic_model)
    box_list = []
    results = model(imgPath, verbose=False)
    result = json.loads((results[0]).tojson())
    for part in result:
        if part["name"] in ["penis", "pussy"]:
            log.debug("检测到: {}".format(part["name"]))
            x = round(part["box"]["x1"])
            y = round(part["box"]["y1"])
            w = round(part["box"]["x2"] - part["box"]["x1"])
            h = round(part["box"]["y2"] - part["box"]["y1"])
            box_list.append([x, y, w, h])
    log.debug(f"使用yolo进行检测完成: {imgPath}, boxList: {box_list}")
    return box_list


def _mosaic_blurry(img, fx, fy, tx, ty, factor=10):  # factor 控制马赛克程度，越小越模糊
    """
    应用标准马赛克效果到指定区域
    factor: 缩小的因子，例如 10 表示缩小到 1/10
    """
    try:
        # 裁剪需要处理的区域
        crop = img.crop((fx, fy, tx, ty))
        crop_w, crop_h = crop.size

        if crop_w <= 0 or crop_h <= 0:
            log.warn(f"尝试对零尺寸区域应用马赛克: ({fx},{fy},{tx},{ty})")
            return img  # 返回原图

        # 缩小图片：计算缩小后的尺寸，确保至少为 1x1
        small_w = max(1, int(crop_w / factor))
        small_h = max(1, int(crop_h / factor))
        small_crop = crop.resize((small_w, small_h), Image.NEAREST)  # 使用 NEAREST 避免插值模糊

        # 放大回原始裁剪区域大小
        mosaic_crop = small_crop.resize(crop.size, Image.NEAREST)  # 同样使用 NEAREST 保持像素块感

        # 将处理后的区域粘贴回原图
        img.paste(mosaic_crop, (fx, fy, tx, ty))
        return img
    except Exception as e:
        log.error(f"应用马赛克到区域 ({fx},{fy},{tx},{ty}) 时出错: {e}")
        return img  # 出错时返回原图


# --- 或者，使用高斯模糊 ---
def _gaussian_blur(img, fx, fy, tx, ty, radius=20):  # radius 控制模糊半径
    """
    应用高斯模糊到指定区域
    """
    try:
        crop = img.crop((fx, fy, tx, ty))
        if crop.width <= 0 or crop.height <= 0:
            log.warn(f"尝试对零尺寸区域应用模糊: ({fx},{fy},{tx},{ty})")
            return img

        blurred_crop = crop.filter(ImageFilter.GaussianBlur(radius))
        img.paste(blurred_crop, (fx, fy, tx, ty))
        return img
    except Exception as e:
        log.error(f"应用高斯模糊到区域 ({fx},{fy},{tx},{ty}) 时出错: {e}")
        return img


# 在 mosaic_blurry 函数中选择调用哪个模糊函数：
# img_copy = _mosaic_blurry(img_copy, fx, fy, tx, ty, factor=15) # 使用马赛克
# 或者
# img_copy = _gaussian_blur(img_copy, fx, fy, tx, ty, radius=25) # 使用高斯模糊


def mosaicBlurry(imgPath: str, image: ImageFile, boxList: list):
    """
    为提供文件保存路径、PIL图片绘制对象、BoxList增加马赛克
    """
    if not boxList:  # 如果没有检测框，直接返回，避免不必要的打开和保存
        log.info(f"未在 {imgPath} 检测到需要打码的区域。")
        return

    # 确保 image 是可修改的，如果传入的是 ImageFile，可能需要 copy()
    # 或者确保调用者传入的是通过 Image.open() 打开的对象
    img_copy = image.copy()  # 操作副本以防意外修改原始对象

    for box in boxList:
        fx = box[0]
        fy = box[1]
        # 确保 tx 和 ty 不超过图片边界
        tx = min(fx + box[2], img_copy.width)
        ty = min(fy + box[3], img_copy.height)
        # 确保 fx, fy, tx, ty 形成有效区域
        if fx < tx and fy < ty:
            img_copy = _mosaic_blurry(
                img_copy,
                fx,
                fy,
                tx,
                ty,
            )
        else:
            log.warn(f"跳过无效的马赛克区域: box={box}, 计算出的边界=({fx},{fy},{tx},{ty})")

    # !!! 在循环结束后，处理完所有 box 再保存 !!!
    try:
        img_copy.save(imgPath)
        log.info(f"已对 {imgPath} 应用马赛克并保存。")
    except Exception as e:
        log.error(f"保存马赛克图片 {imgPath} 失败: {e}")


import os.path

from PIL import Image


def putWatermark(filepath: str, watermarkPath: str):
    # 加载背景图片和叠加的透明 PNG 图片
    # filename = os.path.basename(path)
    srcPath: str = os.path.join(filepath)
    bg = Image.open(srcPath).convert('RGB')  # 背景图片，需要读取为 RGB 格式
    layer = Image.open(watermarkPath).convert('RGBA')  # 叠加的透明 PNG 图片，需要读取为 RGBA 格式

    # 在背景图片上叠加/合成透明 PNG 图片
    bg.paste(layer, (bg.width - layer.width, bg.height - layer.height), layer)

    # 保存结果
    bg.save(filepath)
