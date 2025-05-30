import os

from PIL import Image, ExifTags

from src import log


def clearMetaData(imagePath: str, outputPath: str) -> bool:
    """
    尝试清除 PNG 或 JPEG 图像文件的元数据，并将清理后的图像保存到新路径。

    通过重新保存图像但不包含原始元数据（如 PNG 的 info 字典或 JPEG 的 EXIF）
    来实现元数据清除。

    Args:
        imagePath: 输入图像文件的路径 (PNG 或 JPEG)。
        outputPath: 清理后图像的保存路径。
                     如果与 image_path 相同，将覆盖原始文件（请谨慎使用）。

    Returns:
        True 如果成功处理并保存了图像，否则 False。
    """
    try:
        with Image.open(imagePath) as img:
            original_format = img.format
            log.warn(f"正在处理: {imagePath} (格式: {original_format})")

            # 获取图像原始数据，不包括元数据
            # 对于大多数用例，直接重新保存即可，Pillow默认不会复制所有元数据
            # 特别是当我们不指定 `pnginfo` 或 `exif` 参数时

            if original_format == 'PNG':
                # 重新保存 PNG，不传递 pnginfo 参数
                # 注意：这通常会移除 tEXt, iTXt, zTXt 块。
                # 它可能保留一些基础信息，如尺寸、模式、调色板等，这些不是典型的“元数据”。
                # Pillow 会尝试保留透明度等基本图像特性。
                img.save(outputPath, "PNG")
                log.warn(f"已清除元数据并保存为 PNG: {outputPath}")
                return True

            elif original_format == 'JPEG':
                # 重新保存 JPEG，不传递 exif 参数
                # 注意：这通常会移除 EXIF 数据。可能还会移除 ICC profile 等。
                # 需要注意 JPEG 是有损压缩，每次重新保存都可能降低质量。
                # 可以指定 quality 来控制质量（例如 quality=95）。
                img.save(outputPath, "JPEG", quality=95, subsampling=0)  # subsampling=0 通常质量最高
                log.warn(f"已清除元数据并保存为 JPEG: {outputPath}")
                return True

            else:
                log.warn(f"错误: 不支持的文件格式 {original_format}。仅支持 PNG 和 JPEG。")
                # 你可以选择在这里复制原始文件，或者直接返回失败
                # import shutil
                # shutil.copy2(image_path, output_path)
                # log.warning(f"由于格式不支持，已将原始文件复制到: {output_path}")
                # return True # 如果选择复制，则返回 True
                return False  # 如果选择不支持则失败

    except FileNotFoundError:
        log.warn(f"错误: 输入文件未找到 - {imagePath}")
        return False
    except Image.UnidentifiedImageError:
        log.warn(f"错误: 无法识别的图像文件或文件已损坏 - {imagePath}")
        return False
    except IOError as e:  # 捕获保存时可能发生的错误
        log.warn(f"错误: 保存文件时发生 IO 错误 - {outputPath}: {e}")
        # 清理可能创建的不完整文件
        if os.path.exists(outputPath) and outputPath != imagePath:
            try:
                os.remove(outputPath)
                log.warn(f"已删除不完整的输出文件: {outputPath}")
            except OSError as rm_err:
                log.warn(f"警告: 删除不完整文件失败 {outputPath}: {rm_err}")
        return False
    except Exception as e:
        log.warn(f"处理 {imagePath} 时发生未知错误: {e}")
        return False


def extractMetaData(imagePath: str) -> dict:
    if not os.path.exists(imagePath):
        log.error(f"提取元数据失败，文件不存在:{imagePath}")
    with Image.open(imagePath) as img:
        match img.format:
            case "PNG":
                if hasattr(img, "info") and isinstance(img.info, dict):
                    return img.info.copy()
                else:
                    log.error("未保存元数据")
            case "JPEG":
                metadata = {}
                exif_data_raw = img.getexif()
                if exif_data_raw:
                    for tag_id, value in exif_data_raw.items():
                        tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                        if isinstance(value, bytes):
                            try:
                                metadata[tag_name] = value.decode('utf-8', errors='replace')
                            except UnicodeDecodeError:
                                metadata[tag_name] = repr(value)
                        else:
                            metadata[tag_name] = value
                    return metadata
                else:
                    log.warn(f"在 {imagePath} 中未找到 EXIF 数据。")
            case _:
                log.warn(f"尝试提取的图片不是PNG {imagePath}")
                return {}

    return {}
