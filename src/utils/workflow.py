import json
import os
from typing import Callable, Any, List, Type, Dict

from src import log
from src.config import config


class WorkFlowParser:
    """
    批量对工作流API节点进行批量或顺序操作
    """

    def __init__(self):
        self.workFlow: str = ""

    def reloadFile(self, workflowName: str):
        workflowPath = os.path.join(config.workflow_path,workflowName)
        if not os.path.isfile(workflowPath):
            log.fatal(f"工作流不存在: {workflowPath}")

        with open(workflowPath, mode="r", encoding="utf-8") as f:
            try:
                self.workFlow: str = f.read()
            except Exception as e:
                log.fatal(f"无效的iterScript配置：{e}")

    def reloadWorkFlow(self, wf: str):
        if not isinstance(wf, str):
            log.error(f"重载工作流时遇到了意外错误：{wf}")

        self.workFlow = wf

    @staticmethod
    def _checkFormat(k, v, typ, keyword):
        if not k.startswith(keyword) and not k.endswith(keyword):
            log.error(f"不合法的填充符：{k}")

        if not isinstance(v, typ):
            log.error(f"不合法的填充值：{v}")

    def setStrCustomKey(self, key: str, value: str):
        self._checkFormat(key, value, str, "%")
        self._replace(key, value)

    def setIntCustomKey(self, key: int, value: int):
        """
        设置int值，关键词是11 11
        :param key:
        :param value:
        :return:
        """
        if not isinstance(value, int):
            raise KeyError(f"不合法的填充值：{value}")
        self._replace(str(key), str(value))

    def setUnsafelyNodeID(self, nodeID: str, key: str, value: Any):
        workFlow: dict = json.loads(self.workFlow)

        node = workFlow.get(nodeID)
        inputs = node.get("inputs")
        if not inputs:
            log.fatal(f"setUnsafelyNodeID: 尝试获取{node}的inputs键失败")
        inputs[key] = value

        self.workFlow = json.dumps(workFlow)

    def replace(self, key: str, value):
        self._replace(key, value)

    def _replace(self, key, value):
        self.workFlow = self.workFlow.replace(key, value)

    def getWorkFlow(self) -> str:
        return self.workFlow

    def getAllCustomKeyValueType(self, key: str, valueType: Type) -> List[Any]:
        """
        递归遍历整个工作流JSON结构，查找所有匹配指定键名和值类型的项。

        Args:
            key (str): 要查找的键名。
            valueType (Type): 期望的值的类型 (e.g., str, int, list, dict)。

        Returns:
            List[Any]: 包含所有找到的匹配值的列表。
        """
        try:
            workFlowData = json.loads(self.workFlow)
        except json.JSONDecodeError as e:
            log.error(f"无法解析工作流JSON以查找键 '{key}': {e}")
            return []  # 解析失败返回空列表

        elements: List[Any] = []
        self._recursiveFindKeyValue(workFlowData, key, valueType, elements)
        return elements

    def _recursiveFindKeyValue(self, data: Any, target_key: str, target_type: Type, results: List[Any]):
        """
        递归辅助函数，用于在嵌套结构中查找键值对。

        Args:
            data (Any): 当前正在检查的数据片段（可能是字典、列表或其他类型）。
            target_key (str): 要查找的目标键。
            target_type (Type): 目标值应具有的类型。
            results (List[Any]): 用于收集结果的列表（原地修改）。
        """
        if isinstance(data, dict):
            for k, v in data.items():
                if k == target_key and isinstance(v, target_type):
                    results.append(v)
                # 无论键是否匹配，都需要继续深入遍历值（如果值是容器类型）
                self._recursiveFindKeyValue(v, target_key, target_type, results)
        elif isinstance(data, list):
            for item in data:
                # 遍历列表中的每个元素
                self._recursiveFindKeyValue(item, target_key, target_type, results)
        # 如果 data 不是字典或列表（基本类型），则递归终止于此分支

    # def getAllCustomKeyValueType(self, key: str, valueType) -> List[Any]:
    #     workFlow = json.loads(self.workFlow)
    #     elements: List[Any] = []
    #     for k, v in workFlow.items():
    #         for _k, _v in v.items():
    #             if _k == key and isinstance(_v, valueType):
    #                 elements.append(_v)
    #
    #     return elements

    def setAllCustomKeyValue(self, key: str, function: Callable[[], Any]):
        """
        设置所有的健对应函数生成的值
        :param key:
        :param function:
        :return:
        """
        workFlow = json.loads(self.workFlow)
        randomNumbers: List[int] = []

        def _setAllCustomKeyValue(wf) -> Any:
            if isinstance(wf, dict):
                newDict = {}
                for k, v in wf.items():
                    if k == key:
                        var = function()
                        randomNumbers.append(var)
                        newDict[k] = var
                    else:
                        newDict[k] = _setAllCustomKeyValue(v)
                return newDict
            elif isinstance(wf, list):
                return [_setAllCustomKeyValue(item) for item in wf]
            else:
                return wf

        workFlow = _setAllCustomKeyValue(workFlow)
        self.workFlow = json.dumps(workFlow)
        log.debug(f"设置当前全局键值{key}: {randomNumbers}")
