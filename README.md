# 个人导游智能体 Personal Guide

一个基于Flask的Web应用，根据用户的旅行偏好生成个性化的每日行程计划。

## 功能特性

- 根据城市、日期、预算等参数生成个性化行程
- 支持多种兴趣偏好选择
- 集成Qwen大模型提供智能建议
- 景点历史解说技能：一键生成景点历史沿革、趣味典故与游览贴士
- 本地JSON数据存储景点信息
- 响应式网页设计

## 系统要求

- Python 3.7+
- Flask
- openai
- python-dotenv

## 安装部署

### 1. 克隆项目

```bash
git clone <repository-url>
cd personal-guide
```

### 2. 创建虚拟环境

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# 或者
source venv/bin/activate  # Linux/Mac
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `.env.example` 文件为 `.env` 并填入您的Qwen API密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入您的API密钥：
```
QWEN_API_KEY=your_actual_api_key_here
```

### 5. 运行应用

```bash
python app.py
```

访问 `http://localhost:5000` 查看应用。

## 项目结构

```
personal-guide-student/
├── app.py                     # Flask 主应用入口（3 个路由：/ 、/generate 、/commentary）
├── config.py                  # 配置参考（当前未被 app.py / utils 导入，见下方「代码阅读指引」）
├── requirements.txt           # Python 依赖包列表
├── .env.example               # 环境变量模板，需复制为 .env 后填写
├── .gitignore                 # Git 忽略规则
├── README.md                  # 项目说明文档（本文件）
├── INSTALLATION.md            # 安装指南
│
├── static/                    # 静态资源目录
│   ├── css/
│   │   └── style.css          # 样式文件
│   └── js/
│       └── main.js            # 前端交互脚本（景点历史解说的 fetch 逻辑）
│
├── templates/                 # HTML 模板目录（Jinja2）
│   ├── base.html              # 基础模板
│   ├── index.html             # 主页表单
│   └── result.html            # 结果展示页
│
├── data/
│   └── attractions.json       # 景点基础数据（北京 6 条示例记录）
│
├── utils/                     # 核心逻辑目录
│   ├── ai_client.py           # Qwen API 客户端封装（OpenAI 兼容接口 + enable_search）
│   ├── planner.py             # 行程规划：本地候选筛选 → Qwen 规划 → 本地兜底
│   └── guide.py               # 景点历史解说技能：Prompt 构建 → Qwen → 本地兜底
│
└── skills/                    # 领域流程文档（描述本项目功能的开发/排障约定）
    ├── attraction-history/
    │   └── SKILL.md           # 「景点历史解说」功能的开发流程
    └── bug-fixer/
        └── SKILL.md           # 启动失败 / API 报错的排查流程
```

> 本示例**不含**数据库、单元测试目录、实时地图与天气接口；景点数据全部来自
> `data/attractions.json` 这一个本地 JSON 文件。

### 代码阅读指引（推荐顺序）

1. `app.py` —— 先看 3 个路由分别在做什么，理解「表单 → 后端 → 模板渲染」的闭环。
2. `data/attractions.json` —— 看数据结构，它是后面所有筛选的输入。
3. `utils/planner.py` —— 本项目的核心：`_select_local_candidates()` 做本地可解释打分，
   `_generate_qwen_itinerary()` 构造 Prompt 交给模型，失败时 `_build_local_fallback()` 兜底。
4. `utils/ai_client.py` —— 模型调用统一收口在这里，注意 `enable_search=True`（联网检索）。
5. `utils/guide.py` —— 第二个「技能」，结构与 planner 同构，可对比学习 Prompt + 兜底的写法。
6. `static/js/main.js` + `templates/result.html` —— 前端如何用 `fetch` 调 `/commentary`
   并做 XSS 转义（`escapeHtml`）。

注意：`config.py` 定义了 `Config` 类，但**当前没有任何模块导入它**；真正生效的配置
路径是 `utils/ai_client.py` 里的 `load_dotenv()` + `os.getenv(...)`。阅读时可把它当作
「集中式配置」的对照示例，改动时别误以为改它就能生效。

## 使用说明

1. 访问应用首页
2. 填写旅行偏好信息（城市、日期、预算等）
3. 点击"生成个性化行程"按钮
4. 查看生成的个性化行程计划
5. 点击任一景点的"景点历史解说"按钮，查看该景点的历史沿革、趣味典故与游览贴士
6. 可以修改参数后重新生成

## API集成

本项目集成了阿里云百炼平台的Qwen大模型API，通过OpenAI兼容接口进行调用。API密钥通过环境变量管理，确保安全。

### 景点历史解说技能

- 后端接口：`POST /commentary`，请求体包含景点信息（`name`、`city`、`type`、`description`、`tags`），返回该景点的历史解说 JSON。
- 生成逻辑：`utils/guide.py` 中的 `generate_attraction_history()` 负责构建 Prompt 并调用 Qwen；
- 容错机制：当 Qwen 调用失败时自动回退为本地兜底解说，保证功能可用。

## 安全说明

- API密钥存储在环境变量中，不会出现在代码中
- 所有敏感信息都通过环境变量配置
- 本地数据文件存储景点信息

## 注意事项

- 本项目为简化版本，不包含实时地图、天气等功能
- 景点数据存储在本地JSON文件中
- 生成的行程仅供参考，实际情况可能有所不同

## 已知设计取舍（阅读代码时请注意，非 Bug）

本示例保持原始实现不做修改，以下几处是**有意保留的教学点**，初学者容易在此卡住：

1. **未配置 API Key 时应用无法启动**
   `utils/ai_client.py` 在模块导入阶段就校验 `QWEN_API_KEY` / `QWEN_BASE_URL`，缺失会抛
   `RuntimeError`。因此即使 `planner.py`、`guide.py` 都写了本地兜底逻辑，没有 `.env` 也
   依然起不来服务。想先离线体验，可临时填占位值（见 INSTALLATION.md 常见问题 3），
   此时所有请求都会走本地兜底分支，页面仍能正常渲染。

2. **`app.py` 以 `debug=True, host='0.0.0.0'` 启动**
   `debug=True` 便于教学时看堆栈和自动重载，但它带交互式调试器；绑定 `0.0.0.0` 会把
   服务暴露到局域网。两者组合在真实部署中等于远程代码执行风险。仅在受信任的教室/本机
   环境使用，不要把它当作生产配置范例。

3. **控制台日志非常吵**
   `app.py` 里 `logging.basicConfig(level=logging.DEBUG)` 会把 `httpcore`/`openai` 的逐帧
   HTTP 调试日志一并打出（一次请求可刷上百行）。想只看业务日志，可自行改为
   `level=logging.INFO`，或加 `logging.getLogger("httpcore").setLevel(logging.WARNING)`。

4. **`planner.py` 的两阶段调用链**
   先用 `_select_local_candidates()` 在本地 JSON 里做可解释打分，候选不足时才让模型
   联网补候选，最后再交给模型排定时。看到「两次 API 调用」属正常设计，不是重复代码。

5. **只内置了「北京」的景点数据**
   `data/attractions.json` 仅 6 条北京记录。输入别的城市时本地候选为空，行程完全依赖
   模型联网检索；若模型不可用则会走到「无有效候选数据」兜底提示。可自行扩充城市数据。

## 开发者

本项目为本科通识课程演示项目，旨在展示Flask Web开发和AI集成的基本概念。