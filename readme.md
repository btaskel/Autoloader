<div align="center">

![img_2.png](doc/img/logo_256.png)

## Autoloader : a fully automated creator program for ComfyUI

<br>

</div>

一个为 ComfyUI 用户设计的全自动化内容创作与发布程序。该程序通过读取批量配置文件，自动调用 ComfyUI 生成图片，执行图片后处理（如添加水印、马赛克），提取并处理标签，生成描述，最终将内容自动发布到指定平台（如 Pixiv、Booth）。旨在大幅提高 AI 辅助内容创作者，特别是需要批量操作用户的效率。

**它目前仍然在更新，功能包括且不限于：**
1. 功能全面的Agent 音频、视频、图片 创作流程
2. 更具有内容审查力度的等级
3. 开放api，且具有高并发性
4. 一句话，生成整个创作流程

### 快速开始
    
1. **安装 autoloader**


    git clone https://github.com/btaskel/autoloader.git
    
    cd autoloader
    
    python -m pip install -r requirements.txt

2. 配置工作流

进入comfyui，开启“开发者模式”，点击左上角导出工作流，导出为json文件，放入autoloader/workflow目录下。
 
启动Autoloader

    
    python main.py 

### 配置文件

Autoloader 将配置文件分为了"config.json"以及"script.json"，script可由ai生成

#### script.json:

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