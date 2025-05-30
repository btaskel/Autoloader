import random
from typing import List

from src.config import config
from src.mode_parser.media_post_processor import extraImgPostProcess
from src.socket.websockets_api import Comfyui
from src.mode_parser.upload_block import Order, Image
from src.utils.fileio import makeSuffixDirs
from src.utils.hasher import hashMixSalt
from src.utils.workflow import WorkFlowParser


class FlowParser:
    def __init__(self):
        self._websocket: Comfyui = Comfyui()
        self._wfp: WorkFlowParser = WorkFlowParser()

    def close(self):
        self._websocket.close()

    @staticmethod
    def _initWorkflowParserAndOutputPath() -> str:
        saveDirPath = makeSuffixDirs(config.output_path, "")
        # makeSuffixDirs(config.output_path, "_reviewed")
        return saveDirPath

    def _setWorkFlowBatch(self, batch: int):
        self._wfp.setAllCustomKeyValue("batch_size", lambda: batch)

    def _setWorkflowKey(self, order: Order, fixedSeed: int):
        self._wfp.setAllCustomKeyValue("seed", lambda: random.randint(0, 2 ** 63 - 1))

        for fixedNodeSeedName in order.ui.workflowFixedNodeSeedNames:
            if isinstance(fixedNodeSeedName, str):
                self._wfp.setUnsafelyNodeID(fixedNodeSeedName, "seed", fixedSeed)
                continue
            if isinstance(fixedNodeSeedName, int):
                self._wfp.setUnsafelyNodeID(str(fixedNodeSeedName), "seed", fixedSeed)
                continue
            order.ui.error(f"固定的节点种子名称类型错误: {fixedNodeSeedName} {type(fixedNodeSeedName)}")

    def _requestComfyui(self, order: Order, saveDirPath: str):
        def _requestLoop() -> List[str]:
            def __requestLoop(images: List[Image]) -> List[str]:
                __batch = len(images)
                if not __batch:
                    order.ui.fatal("无效的批次数量: 0")

                __result: List[str] = []

                self._wfp.reloadFile(images[0].workflowName)  # 如果一个批次包含多个Image，则只使用第一个的工作流
                self._setWorkFlowBatch(__batch)
                self._setWorkflowKey(order, seed)
                comfyuiFilePaths, taskInfo = self._websocket.send(self._wfp.getWorkFlow(), saveDirPath)
                order.taskInfo = taskInfo
                __result.extend(comfyuiFilePaths)
                order.saveOrder()
                return __result

            if order.ui.workflowUniformString:
                seed = hashMixSalt(order.ui.workflowUniformString)
            else:
                seed = random.randint(0, 2 ** 63 - 1)

            _result: List[str] = []
            _activeImages = order.sortByActive()

            _loop = int(len(_activeImages) / order.ui.batch)
            _singleLoop = len(_activeImages) % order.ui.batch
            if not _loop and not _singleLoop:
                order.ui.fatal(f"无效的批次分解: 将{order.ui.number} / {order.ui.batch}的商{_loop}余{_singleLoop}")

            for _ in range(_loop):
                order.ui.info(f"剩余 {_loop} 次 {order.ui.batch} 批次comfyui请求")
                _result.extend(__requestLoop(_activeImages[:order.ui.batch]))
                _activeImages = _activeImages[order.ui.batch:]
                _loop -= 1

            for _ in range(_singleLoop):
                order.ui.info(f"剩余 {_singleLoop} 次 单批次comfyui请求")
                _result.extend(__requestLoop(_activeImages[:1]))
                _activeImages = _activeImages[1:]
                _singleLoop -= 1

            return _result

        activeImages = order.sortByActive()
        if activeImages:
            order.ui.debug(f"活动的images对象数量: {len(activeImages)}")
            result = _requestLoop()
            for activeImage in activeImages:
                activeImage.outputPath = result.pop(0)

        counter = 0
        for activeImage in order.sortByActive():
            if not activeImage.outputPath:
                counter += 1
        if counter:
            order.ui.fatal(f"没有将所有的活动的Image对象填充outputPath: 对象数量: {counter}")

    def append(self, order: Order):
        saveDirPath = self._initWorkflowParserAndOutputPath()
        order.ui.debug("_requestComfyui")
        self._requestComfyui(order, saveDirPath)
        order.ui.debug("_extraImgPostProcess")
        extraImgPostProcess(order)
        order.sort()
