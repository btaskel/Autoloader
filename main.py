import time
from typing import List

from src import log
from src.config import config
from src.mode_parser.flow_parser import FlowParser
from src.mode_parser.upload_block import Order, loadOrderSave, loadOrders
from src.uploader.uploader import Uploader
from src.utils.fileio import getFilesSortedByMtime


def getOrderSave() -> (Order, str):
    orderSavePaths = getFilesSortedByMtime(config.order_path)
    if orderSavePaths:
        orderSavePath = orderSavePaths.pop()
        orderSave, mode = loadOrderSave(orderSavePath)
        if not len(orderSave.getOutputFilePath()):
            return orderSave, mode
    return None, None


def loadScript() -> (List[Order], str):
    order: Order
    mode: str
    order, mode = getOrderSave()
    if order:
        log.debug("检测到失败的order_script记录，正在尝试恢复")
        return [order], mode
    else:
        log.debug("尝试使用config中的order_script")
        return loadOrders(config.script_path)


def main():
    mode: str
    orders, mode = loadScript()
    uploader = Uploader()

    def flowParser(_orders: List[Order]):
        flower = FlowParser()
        while len(_orders):
            _order = _orders.pop(0)
            _order.ui.info("开始执行")
            flower.append(_order)
            uploader.append(_order)
        time.sleep(0.5)
        flower.close()

    def randomParser():
        pass

    match mode.lower():
        case "flow":
            flowParser(orders)
        case _:
            log.warn(f"未知的处理模式: {mode}, 尝试使用默认模式: flow")
            flowParser(orders)
            pass
    log.info("执行完毕")


if __name__ == '__main__':
    main()
