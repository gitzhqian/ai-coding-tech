# 个人导游智能体 Personal Guide - 安装指南

## 项目概述

个人导游智能体是一个基于Flask的Web应用，根据用户的旅行偏好生成个性化的每日行程计划。

## 安装步骤

### 1. 环境要求

- Python 3.7+
- pip (Python包管理器)

### 2. 克隆项目

```bash
git clone <repository-url>
cd personal-guide
```

### 3. 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

如果遇到网络问题，可以使用国内镜像源：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

### 5. 配置环境变量

复制示例环境文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入您的API密钥：

```bash
# Windows PowerShell:
Copy-Item .env.example .env

# macOS / Linux:
cp .env.example .env
```

### 6. 运行应用

```bash
python app.py
```

应用将在 `http://localhost:5000` 上运行。

## 项目结构

```
personal-guide-student/
├── app.py                     # Flask主应用入口
├── config.py                  # 配置参考（当前未被任何模块导入）
├── requirements.txt           # Python依赖包列表
├── .env.example               # 环境变量模板（复制为 .env 使用）
├── INSTALLATION.md            # 安装指南
├── README.md                  # 项目说明文档
│
├── static/                    # 静态资源目录
│   ├── css/
│   │   └── style.css          # 样式文件
│   └── js/
│       └── main.js            # 前端交互脚本（含景点历史解说）
│
├── templates/                 # HTML模板目录
│   ├── base.html              # 基础模板
│   ├── index.html             # 主页表单
│   └── result.html            # 结果展示页
│
├── data/                      # 数据文件目录
│   └── attractions.json       # 景点基础数据
│
├── utils/                     # 工具函数目录
│   ├── ai_client.py           # AI客户端封装
│   ├── planner.py             # 行程规划工具
│   └── guide.py               # 景点历史解说技能
│
└── skills/                    # 领域流程文档
    ├── attraction-history/    # 景点历史解说功能的开发约定
    └── bug-fixer/             # 故障排查流程
```

## 功能说明

### 用户输入参数

- **目的城市**: 用户旅行的目的地
- **旅行日期**: 出行的具体日期
- **开始时间/结束时间**: 当日旅行的时间范围
- **预算**: 旅行预算金额
- **兴趣偏好**: 用户感兴趣的活动类型
- **饮食偏好**: 用户的饮食喜好
- **交通方式**: 偏好的出行方式
- **旅行节奏**: 旅行的快慢节奏

### 生成的行程内容

- **时间安排**: 每个景点的具体时间
- **景点信息**: 名称、类型、描述、地点
- **推荐理由**: 为什么推荐该景点
- **交通建议**: 景点间的交通方式
- **预计费用**: 景点门票、餐饮等费用
- **旅行提示**: 实用的旅行建议
- **景点历史解说**: 点击景点旁的“景点历史解说”按钮，即可查看该景点的历史沿革、趣味典故、必看亮点与游览贴士

## API集成

项目集成了阿里云百炼平台的Qwen大模型API，通过OpenAI兼容接口进行调用。API密钥通过环境变量管理，确保安全。

## 常见问题

### 1. 安装依赖时出现网络错误

使用国内镜像源安装：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

### 2. 端口被占用

如果5000端口被占用，可以在app.py中修改端口号：

```python
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)  # 修改端口
```

### 3. 启动即报 `RuntimeError: 未检测到 QWEN_API_KEY`

原因：`utils/ai_client.py` 在**导入阶段**就校验配置，`.env` 不存在或缺项时立刻抛错，
Flask 还没来得及启动。请先确认已完成第 5 步（复制 `.env.example` 为 `.env`）并填写了
`QWEN_API_KEY` 与 `QWEN_BASE_URL`。

**没有 API Key 也想先跑通界面？** 在 `.env` 里填占位值即可：

```
QWEN_API_KEY=sk-placeholder-not-a-real-key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
```

这样应用能正常启动，所有请求会因为鉴权失败而自动走 `planner.py` / `guide.py` 里的
本地兜底分支：行程页仍会渲染出来，只是内容标注为「本地解说模式 / 兜底」，
`candidate_source` 会显示无有效候选数据。这是离线演示和排障时的常用手段。

### 4. 中文乱码或 `UnicodeEncodeError: 'gbk' codec can't encode ...`

Windows 中文版控制台默认编码是 GBK，而项目源文件均为 UTF-8。处理方式：

```powershell
# PowerShell
$env:PYTHONIOENCODING = "utf-8"
chcp 65001
```

```cmd
:: cmd
set PYTHONIOENCODING=utf-8
chcp 65001
```

建议同时把编辑器（VS Code 等）的文件编码固定为 UTF-8，避免保存时把中文注释写成乱码。

### 5. `ModuleNotFoundError: No module named 'httpx'`

说明依赖没装全或装到了别的解释器里。先确认虚拟环境已激活（命令行提示符前有 `(venv)`），
再执行 `pip install -r requirements.txt`。可用下面两条核对解释器与包路径是否一致：

```bash
python -c "import sys; print(sys.executable)"
pip -V
```

### 6. 提交表单后提示「找不到景点数据文件」

`app.py` 以**相对路径** `data/attractions.json` 读取景点数据，因此必须在项目根目录下
启动服务。请先 `cd` 到含 `app.py` 的目录再运行 `python app.py`；若在 IDE 里配置运行
配置，需把工作目录（cwd）设为项目根目录。

## 开发与扩展

### 添加新城市数据

在`data/attractions.json`中添加新的城市景点数据：

```json
{
  "id": 7,
  "name": "外滩",
  "city": "上海",
  "type": "风景名胜",
  "rating": 4.7,
  "price": 0,
  "duration": 2,
  "description": "上海最具代表性的地标之一",
  "location": "上海市黄浦区中山东一路",
  "tags": ["风景", "历史文化", "夜景"]
}
```

### 自定义行程规划算法

修改`utils/planner.py`中的`generate_personalized_itinerary`函数来自定义行程规划逻辑。

## 技术栈

- **后端**: Python + Flask
- **前端**: HTML/CSS/JavaScript
- **数据存储**: JSON文件
- **AI服务**: 阿里云Qwen API
- **环境管理**: python-dotenv

## 版权声明

本项目仅供学习和演示使用。