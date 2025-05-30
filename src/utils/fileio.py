import os
import zipfile
from datetime import datetime
from typing import List, Optional


def getDateTimeSuffixPath(suffix: str) -> str:
    date = datetime.now()
    return str(date.year) + "_" + str(date.month) + "_" + str(date.day) + suffix


def getSuffixPath(suffix: str) -> str:
    date = datetime.now()
    return f"{date.year}-{date.month}-{date.day}_{date.hour}-{date.minute}-{suffix}"


def makeSuffixDirs(path: str, suffix: str) -> str:
    outputPath = os.path.join(path, getDateTimeSuffixPath(suffix))
    if not os.path.exists(outputPath):
        os.makedirs(outputPath)
    return outputPath


def getFilesSortedByMtime(directory_path, reverse=False) -> List[str]:
    """获取目录中所有文件，按修改时间排序。"""
    try:
        all_entries = [os.path.join(directory_path, f) for f in os.listdir(directory_path)]
        files = [f for f in all_entries if os.path.isfile(f)]
        files.sort(key=os.path.getmtime, reverse=reverse)
        return files
    except Exception as e:
        print(f"处理目录 '{directory_path}' 时出错: {e}")
        return []


def stringToBinaryBytes(
        text: str,
        errors: str = 'strict'
) -> bytes:
    """
    将字符串按照指定的编码转换为 bytes 对象。

    这模拟了将字符串写入文件（使用指定编码）然后以二进制
    模式 ('rb') 读回该文件的过程，但完全在内存中进行。

    Args:
        text: 要转换的输入字符串。
        errors: 指定如何处理编码错误的策略。常见的选项有：
                - 'strict': 如果有无法编码的字符，则引发 UnicodeEncodeError (默认)。
                - 'ignore': 忽略无法编码的字符。
                - 'replace': 用替换标记（通常是 '?'）替换无法编码的字符。
                - 'xmlcharrefreplace': 用 XML 字符引用替换。
                - 'backslashreplace': 用反斜杠转义序列替换。

    Returns:
        一个 bytes 对象，包含字符串按指定编码表示的原始字节序列。
        如果在编码过程中发生错误（例如，无效的编码名称或
        在 'strict' 模式下遇到无法编码的字符），则打印错误消息并返回 None。

    Raises:
        (内部处理) LookupError: 如果提供的 encoding 名称无效。
        (内部处理) UnicodeEncodeError: 如果在 errors='strict' 模式下，
                                    字符串包含无法用指定编码表示的字符。
    """
    try:
        # 核心操作：使用 encode() 方法进行转换
        binary_data = text.encode(encoding="utf-8", errors=errors)
        return binary_data
    except UnicodeEncodeError as e:
        print(f"错误：字符串中包含无法使用编码 \"utf-8\" (模式: '{errors}') 表示的字符。")
        print(f"详细信息: {e}")
        return bytes()
    except Exception as e:
        # 捕获其他潜在的意外错误
        print(f"转换过程中发生意外错误: {e}")
        return bytes()


def createFile(path: str, content: str):
    with open(path, mode="w+", encoding="utf-8") as f:
        f.write(content)


def compressFilesToZip(filePaths: List[str], outputZipPath: str) -> Optional[str]:
    """
    将列表中的多个文件压缩到一个指定的 ZIP 文件中。

    如果输出 ZIP 文件已存在，它将被覆盖。

    Args:
        filePaths: 一个包含需要压缩的文件完整路径的列表。
        outputZipPath: 要创建的 ZIP 文件的完整路径。

    Returns:
        成功时返回创建的 ZIP 文件的完整路径 (output_zip_path)，
        如果列表为空、任何文件不存在、输出目录无效或发生错误，则返回 None。
    """
    # 1. 检查输入列表是否为空
    if not filePaths:
        print("错误：输入的文件路径列表为空。")
        return None

    # 2. 验证所有输入文件是否存在且是文件
    for file_path in filePaths:
        if not os.path.exists(file_path):
            print(f"错误：输入文件 '{file_path}' 不存在。")
            return None
        if not os.path.isfile(file_path):
            print(f"错误：输入路径 '{file_path}' 不是一个有效的文件。")
            return None

    # 3. 验证输出 ZIP 文件的目录是否存在
    output_dir = os.path.dirname(outputZipPath)
    # 如果输出路径只包含文件名（没有目录），则目录为空字符串 ''
    # os.path.exists('') 返回 False，这是我们想要的
    # 如果目录非空，则检查它是否存在且是目录
    if output_dir and not os.path.isdir(output_dir):
        print(f"错误：输出目录 '{output_dir}' 不存在或不是一个有效的目录。")
        # 或者，你可以选择创建目录：
        # try:
        #     os.makedirs(output_dir, exist_ok=True)
        #     print(f"已创建输出目录: '{output_dir}'")
        # except OSError as e:
        #     print(f"错误：无法创建输出目录 '{output_dir}': {e}")
        #     return None
        return None # 当前选择不自动创建目录

    # 4. 执行压缩
    try:
        print(f"开始将 {len(filePaths)} 个文件压缩到 '{outputZipPath}'...")
        # 使用 'w' 模式创建或覆盖 zip 文件
        # 使用 zipfile.ZIP_DEFLATED 进行压缩
        with zipfile.ZipFile(outputZipPath, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
            # 遍历文件列表并将每个文件添加到 zip 存档中
            for file_path in filePaths:
                # arcname 指定文件在 zip 存档中的名称（这里使用原始文件名）
                # 这可以防止在 zip 文件中创建不必要的目录结构
                archive_name = os.path.basename(file_path)
                zipf.write(file_path, arcname=archive_name)
                print(f"  - 已添加: '{file_path}' (作为 '{archive_name}')")

        print(f"所有文件已成功压缩到: '{outputZipPath}'")
        return outputZipPath # 返回指定的输出 zip 文件路径

    except FileNotFoundError as e:
        # 理论上已被前面的检查覆盖，但为了健壮性保留
        print(f"错误: 压缩过程中找不到文件 '{e.filename}'。")
        return None
    except zipfile.BadZipFile:
        print(f"错误: 创建或写入 zip 文件 '{outputZipPath}' 失败。")
        return None
    except OSError as e:
        print(f"错误: 发生文件系统错误: {e}")
        return None
    except Exception as e:
        print(f"压缩过程中发生意外错误: {e}")
        return None


if __name__ == '__main__':
    print(stringToBinaryBytes("testabcdedf"))
