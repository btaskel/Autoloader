# src/utils/uploader/dropbox_uploader.py

import os
import random
import time
import traceback
from typing import Optional, Literal

import dropbox
import requests
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import WriteMode, CommitInfo, FileMetadata
from dropbox.sharing import SharedLinkMetadata, SharedLinkSettings, RequestedVisibility, LinkAudience, AccessLevel, \
    ListSharedLinksResult, CreateSharedLinkWithSettingsError, LinkPermissions, FolderLinkMetadata
# 假设 SDK 内部可能使用 requests 或类似库，也可能抛出网络相关异常
from requests.exceptions import RequestException

# 假设你的日志和配置模块路径如下
from src import log
from src.config import config
from src.uploader.payloadbase import PayloadBase

# 为大文件分块上传定义常量
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB，可以根据需要调整
MAX_FILE_SIZE_FOR_SIMPLE_UPLOAD = 150 * 1024 * 1024  # 150MB，Dropbox API 限制


class DropboxPayload(PayloadBase):
    def __init__(self):
        super().__init__()
        self.folderName: str = ""
        self.shareEnable: bool = False


class DropboxUploader:
    """
    使用 Dropbox 官方 SDK 上传文件到 Dropbox。
    包含重试逻辑和对大文件的分块上传支持。
    """

    def __init__(self, access_token: str):
        """
        初始化 Dropbox Uploader。

        Args:
            access_token (str): 用于认证的 Dropbox API 访问令牌。
                                建议从安全配置中获取，例如 src.config。
        """
        if not access_token:
            log.error("Dropbox Access Token 未提供，无法初始化 Uploader。")
            raise ValueError("Dropbox Access Token 不能为空。")

        self.access_token = access_token
        session = requests.session()
        session.proxies = config.proxies
        try:
            # 初始化 Dropbox 客户端
            self.dbx = dropbox.Dropbox(self.access_token, session=session)
            # 测试连接和认证（可选，但推荐）
            self.dbx.users_get_current_account()
            log.info("Dropbox 客户端初始化成功并验证通过。")
        except AuthError as e:
            log.error(f"Dropbox 认证失败: {e}. 请检查 Access Token 是否有效或过期。")
            # 可以选择在这里抛出异常，或者让后续操作失败
            raise ConnectionAbortedError(f"Dropbox 认证失败: {e}") from e
        except Exception as e:
            log.error(f"初始化 Dropbox 客户端时发生未知错误: {e}")
            log.error(traceback.format_exc())
            # 根据需要处理或重新抛出异常
            raise ConnectionAbortedError(f"初始化 Dropbox 客户端失败: {e}") from e

    @staticmethod
    def _retry_operation(task_func, operation_description="Dropbox 操作", max_retries=5, base_delay=1, max_delay=32):
        """
        通用的重试逻辑，用于包装可能失败的 Dropbox API 调用。

        Args:
            task_func (callable): 要执行的操作函数（无参数）。
            operation_description (str): 操作的描述，用于日志记录。
            max_retries (int): 最大重试次数。
            base_delay (int): 初始延迟（秒）。
            max_delay (int): 最大延迟（秒）。

        Returns:
            任意: task_func 的返回值，如果成功。
            None: 如果重试次数用尽后仍然失败。
        """
        retries = 0
        delay = base_delay

        while retries < max_retries:
            try:
                log.debug(f"尝试执行: {operation_description}")
                result = task_func()
                log.debug(f"{operation_description} 成功。")
                return result
            # 处理 Dropbox 特定的 API 错误 (例如速率限制、服务器内部错误等)
            except ApiError as e:
                log.warn(f"{operation_description} 发生 API 错误: {e}")
                # 特定错误处理：例如，如果是速率限制，错误对象中会有 retry_after 信息
                if e.error.is_rate_limit_error():
                    retry_after = e.error.get_rate_limit_error().retry_after
                    log.warn(f"触发速率限制，将在 {retry_after} 秒后重试...")
                    time.sleep(retry_after + random.uniform(0, 1))  # 加一点随机性
                    # 不增加常规重试次数或延迟，遵循 API 指示
                    continue  # 直接进入下一次循环尝试
                # 其他可重试的 API 错误 (根据需要添加判断)
                # if e.error.is_internal_server_error() or ... :
                #    pass # 继续执行下面的重试逻辑

            # 处理网络层面的错误 (例如连接超时、DNS 问题)
            except RequestException as e:
                log.warn(f"{operation_description} 发生网络错误: {e}")
                # 网络错误通常适合重试

            # 处理其他潜在异常
            except Exception as e:
                log.error(f"{operation_description} 发生未预料的错误:\n>>>>>")
                traceback.print_exc()
                log.error("<<<<<")
                # 对于未知错误，可能不应该无限重试，但这里遵循原始逻辑
                # 可以根据需要决定是否对某些 Exception 提前退出

            # 如果需要重试
            retries += 1
            if retries >= max_retries:
                log.error(f"[重试] {operation_description} 重试次数用尽 ({max_retries}), 放弃。")
                return None  # 表示失败

            # 计算延迟：指数退避 + 随机抖动
            current_delay = min(delay * (2 ** (retries - 1)), max_delay)
            current_delay += random.uniform(0, current_delay * 0.3)  # 增加随机抖动
            log.info(f"{operation_description} 失败，将在 {current_delay:.2f} 秒后重试 ({retries}/{max_retries})...")
            time.sleep(current_delay)

        return None  # 理论上不会执行到这里，但在循环结束后明确返回 None

    def uploadFile(self, local_path: str, dropbox_path: str) -> Optional[FileMetadata]:
        """
        上传单个文件到 Dropbox 指定路径。
        自动处理大文件分块上传。

        Args:
            local_path (str): 本地文件的完整路径。
            dropbox_path (str): 文件在 Dropbox 中的目标路径 (必须以 / 开头，并且路径分隔符必须是 / )。

        Returns:
            Optional[FileMetadata]: 上传成功则返回文件的元数据对象，失败则返回 None。
        """
        # 确保 dropbox_path 以 '/' 开头
        if not dropbox_path.startswith('/'):
            original_path = dropbox_path
            dropbox_path = '/' + dropbox_path
            log.debug(f"Dropbox 路径 '{original_path}' 不以 '/' 开头，已自动修正为 '{dropbox_path}'。")

        dropbox_path.replace('\\', '/')

        # 检查本地文件是否存在
        if not os.path.exists(local_path):
            log.error(f"本地文件不存在，无法上传: {local_path}")
            return None

        file_size = os.path.getsize(local_path)
        log.info(f"准备上传文件: '{local_path}' ({file_size / 1024 / 1024:.2f} MB) 到 Dropbox 路径: '{dropbox_path}'")

        # 根据文件大小选择上传方式
        if file_size <= MAX_FILE_SIZE_FOR_SIMPLE_UPLOAD:
            log.debug("使用单次上传方法 (files_upload)。")
            return self._upload_small_file(local_path, dropbox_path)
        else:
            log.debug(f"文件大小超过 {MAX_FILE_SIZE_FOR_SIMPLE_UPLOAD / 1024 / 1024:.0f} MB，使用分块上传方法。")
            return self._upload_large_file(local_path, dropbox_path, file_size)

    def _ensure_folder_exists(self, dropbox_folder_path: str) -> bool:
        """
        确保指定的 Dropbox 文件夹存在，如果不存在则尝试创建它。
        这是一个辅助方法，主要被 share_folder 调用，或者在上传前确保目标文件夹存在。
        """
        if not dropbox_folder_path.startswith('/'):
            dropbox_folder_path = '/' + dropbox_folder_path
            log.warn(f"确保文件夹存在: 路径 '{dropbox_folder_path}' 不以 '/' 开头，已自动修正。")

        operation_desc = f"检查或创建文件夹 '{dropbox_folder_path}'"

        def task():
            try:
                # 尝试获取文件夹元数据
                self.dbx.files_get_metadata(dropbox_folder_path, include_deleted=False)
                log.debug(f"文件夹 '{dropbox_folder_path}' 已存在。")
                return True  # 文件夹已存在
            except ApiError as e:
                if e.error.is_path() and e.error.get_path().is_not_found():
                    log.info(f"文件夹 '{dropbox_folder_path}' 不存在，尝试创建...")
                    try:
                        # 如果文件夹不存在，创建它
                        self.dbx.files_create_folder_v2(dropbox_folder_path)
                        log.info(f"文件夹 '{dropbox_folder_path}' 创建成功。")
                        return True  # 文件夹创建成功
                    except ApiError as create_e:
                        # 处理创建文件夹时可能发生的冲突（例如，如果文件夹在检查和创建之间被另一个操作创建了）
                        if create_e.error.is_path() and create_e.error.get_path().is_conflict():
                            log.warn(f"创建文件夹 '{dropbox_folder_path}' 时发生冲突，可能已由其他操作创建。假设存在。")
                            # 再次检查元数据以确认
                            try:
                                self.dbx.files_get_metadata(dropbox_folder_path)
                                return True  # 确认存在
                            except ApiError:
                                log.error(f"创建文件夹 '{dropbox_folder_path}' 冲突后仍无法确认其存在。")
                                raise create_e  # 重新抛出创建错误
                        else:
                            log.error(f"创建文件夹 '{dropbox_folder_path}' 失败: {create_e}")
                            raise create_e  # 重新抛出创建错误
                else:
                    # 其他类型的 ApiError（例如权限问题）
                    log.error(f"检查文件夹 '{dropbox_folder_path}' 元数据时出错: {e}")
                    raise e  # 重新抛出原始错误

        result = self._retry_operation(task, operation_desc)
        return result is True

    def create_shared_link(self, dropbox_path: str) -> Optional[str]:
        """
        为指定的 Dropbox 路径创建共享链接。
        如果共享链接已存在，则尝试获取现有的共享链接。

        Args:
            dropbox_path (str): Dropbox 中的文件或文件夹路径，必须以 '/' 开头。

        Returns:
            Optional[str]: 共享链接的 URL，如果失败则返回 None。
        """
        # 确保 dropbox_path 以 '/' 开头
        if not dropbox_path.startswith('/'):
            original_path = dropbox_path
            dropbox_path = '/' + dropbox_path
            log.warn(f"Dropbox 路径 '{original_path}' 不以 '/' 开头，已自动修正为 '{dropbox_path}'。")

        dropbox_path = dropbox_path.replace('\\', '/')

        operation_desc = f"创建共享链接 for '{dropbox_path}'"

        def task():
            try:
                metadata = self.dbx.sharing_create_shared_link_with_settings(dropbox_path)
                return metadata.url
            except ApiError as e:
                if e.error.is_create_shared_link_with_settings_error():
                    error = e.error.get_create_shared_link_with_settings_error()
                    if error.is_shared_link_already_exists():
                        # 尝试获取现有的共享链接
                        try:
                            links = self.dbx.sharing_list_shared_links(path=dropbox_path, direct_only=True)
                            if links.links:
                                return links.links[0].url
                            else:
                                log.error(f"无法获取已存在的共享链接 for '{dropbox_path}'")
                                return None
                        except ApiError as list_e:
                            log.error(f"获取共享链接列表失败: {list_e}")
                            return None
                    else:
                        log.error(f"创建共享链接失败: {error}")
                        return None
                else:
                    log.error(f"API 错误: {e}")
                    return None

        url = self._retry_operation(task, operation_desc)
        if url:
            log.info(f"成功获取共享链接: {url}")
        else:
            log.error(f"获取共享链接失败 for '{dropbox_path}'")
        return url

    def startUpload(self, payload: DropboxPayload) -> str:
        files = payload.getFiles()
        if not files:
            log.error("没有任何文件需要上传")
            return ""
        for file in files:
            basename = os.path.basename(file)
            self.uploadFile(file, f"{payload.folderName}/{basename}")

        url = self.create_shared_link(payload.folderName)
        return url

    def _upload_small_file(self, local_path: str, dropbox_path: str) -> Optional[FileMetadata]:
        """处理小文件的单次上传"""
        operation_desc = f"单次上传 '{os.path.basename(local_path)}' 到 '{dropbox_path}'"

        def task():
            # 使用 'with' 确保文件正确关闭
            with open(local_path, 'rb') as f:
                # mode=WriteMode('overwrite') 表示如果文件已存在则覆盖
                # 其他模式如 'add' (如果存在则不上传并报错) 或 'update' (如果存在则基于 rev 更新)
                metadata = self.dbx.files_upload(
                    f.read(),
                    dropbox_path,
                    mode=WriteMode('overwrite'),
                    # 可以设置 client_modified 时间等，如果需要
                    # client_modified=datetime.datetime(*time.gmtime(os.path.getmtime(local_path))[:6]),
                    mute=True  # 避免在用户文件活动中产生通知
                )
                return metadata

        metadata = self._retry_operation(task, operation_desc)

        if metadata:
            log.info(f"文件 '{metadata.name}' 成功上传到 Dropbox: {metadata.path_display}")
            return metadata
        else:
            log.error(f"上传文件 '{os.path.basename(local_path)}' 到 '{dropbox_path}' 失败。")
            return None

    def _upload_large_file(self, local_path: str, dropbox_path: str, file_size: int) -> Optional[FileMetadata]:
        """处理大文件的分块上传"""
        operation_desc = f"分块上传 '{os.path.basename(local_path)}' 到 '{dropbox_path}'"

        def task():
            # 使用 'with' 确保文件正确关闭
            with open(local_path, 'rb') as f:
                # 1. 开始上传会话
                log.debug(f"开始分块上传会话...")
                try:
                    upload_session_start_result = self.dbx.files_upload_session_start(f.read(CHUNK_SIZE))
                    cursor = dropbox.files.UploadSessionCursor(session_id=upload_session_start_result.session_id,
                                                               offset=f.tell())
                    commit = CommitInfo(path=dropbox_path, mode=WriteMode('overwrite'), mute=True)
                    log.debug(f"会话已开始: {cursor.session_id}, 已上传 {cursor.offset / 1024 / 1024:.2f} MB")
                except ApiError as e:
                    log.error(f"启动上传会话失败: {e}")
                    raise  # 抛出让 _retry_operation 捕获并处理重试

                # 2. 循环追加数据块
                while f.tell() < file_size:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        # 文件读取意外结束？
                        log.warn("读取到空数据块，但文件未结束，可能存在问题。")
                        break

                    # 重试上传数据块的逻辑可以更精细地放在这里，
                    # 但为了简化，我们让外层的 _retry_operation 处理整个 task 的重试
                    try:
                        self.dbx.files_upload_session_append_v2(chunk, cursor)
                        cursor.offset = f.tell()
                        log.debug(
                            f"已追加数据块，总上传: {cursor.offset / 1024 / 1024:.2f} MB / {file_size / 1024 / 1024:.2f} MB")
                    except ApiError as e:
                        # 如果是 session not found 等错误，可能需要从头开始，外层重试会处理
                        log.warn(f"追加数据块失败: {e}. 将由外层重试机制处理。")
                        raise  # 抛出让 _retry_operation 捕获

                    # （可选）添加短暂休眠以避免速率限制，或根据 ApiError 中的 retry_after
                    # time.sleep(0.1)

                # 3. 完成上传会话
                log.debug(f"所有数据块上传完毕，正在完成会话...")
                try:
                    metadata = self.dbx.files_upload_session_finish(b'', cursor, commit)  # data 参数为空字节串
                    log.debug("分块上传会话成功完成。")
                    return metadata
                except ApiError as e:
                    log.error(f"完成上传会话失败: {e}")
                    # 特别处理 commit 冲突等情况？
                    # if e.error.is_path() and e.error.get_path().reason.is_conflict():
                    #    log.error("目标路径冲突，无法完成上传。")
                    raise  # 抛出让 _retry_operation 捕获

        metadata = self._retry_operation(task, operation_desc)

        if metadata:
            log.info(f"大文件 '{metadata.name}' 通过分块上传成功到 Dropbox: {metadata.path_display}")
            return metadata
        else:
            log.error(f"分块上传文件 '{os.path.basename(local_path)}' 到 '{dropbox_path}' 最终失败。")
            return None
