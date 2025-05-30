from src.aigc.base import client, parseLlmJsonRobustly

_template = """
根据以下json格式，和用户输入信息生成一个脚本文件，不允许出现注释、这是示例:
{
  "global": { // 全局处理块
    "delete_files_enable": false todo: // 自动删除已经上传的文件
  },
  "mode": "flow", // 处理模式(默认flow): flow-按顺序执行
  "uploads": [ // 上传配置块
    {
      "target": { // 上传目标
        "website_name": "pixiv", // 上传的目标网站
        "packer_enable": false, // 是否打包成压缩文件上传
        "packer_start_pos": 1, // 打包开始的索引位置, 1表示从第二个文件开始打包
        "caption": "这是描述内容", // 上传的描述
        "extension_file_context": "", // 附加的文件的内容
      },
      "workflow": {
        "workflow_name": "", // 要执行的workflow文件名称, 为空则根据 sfw_level_num 等级自动选择合适的workflow
        "fixed_node_seed_name": ["16","11"], // 在workflow中固定多个节点的种子id
        "uniform_string": "" // 统一标识字符，当前程序运行期间会生成全局固定盐，根据该字符的整数结果固定全局种子为某一类型
      },
      "number": 3, // 生成图片的总数量
      "batch": 2, // 一次生成的批次，在充分利用vram的情况下可以适当增加, 以提高并行性能
      "safety_cover_sfw_level_num": 2, // 封面安全工作等级: 0~2 数字越高, 安全系数越高
      "sfw_level_num": 1, // 安全工作等级: 0~2 数字越高, 安全系数越高
      "watermark_enable": true, // 外置水印是否启用
      "mosaic_enable": true // 外置马赛克是否启用
    },
    ...... // 其他上传配置块
  ]
}
"""


def generateScript() -> dict:
    """
    使用llm生成脚本
    :return:
    """
    response = client.genContent("gemini-2.5-flash-preview-04-17", _template)
    scriptContentDc = parseLlmJsonRobustly(response)
    return scriptContentDc
