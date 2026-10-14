import json
import logging
import os

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

if not QWEN_API_KEY:
    raise RuntimeError(
        "未检测到 QWEN_API_KEY。请在项目根目录 .env 中配置 QWEN_API_KEY。"
    )

if not QWEN_BASE_URL:
    raise RuntimeError(
        "未检测到 QWEN_BASE_URL。请在项目根目录 .env 中配置 QWEN_BASE_URL。"
    )

# 不继承 Windows 系统代理，避免 127.0.0.1:7897 等本地代理干扰百炼调用。
_http_client = httpx.Client(
    trust_env=False,
    timeout=60.0,
)

client = OpenAI(
    api_key=QWEN_API_KEY,
    base_url=QWEN_BASE_URL,
    http_client=_http_client,
)


def call_qwen_api(prompt, system_prompt="你是一个个性化旅行规划智能体。"):
    """
    调用 Qwen Chat Completions。
    planner.py 的动态候选检索和最终行程规划都会调用此函数。

    返回：
        str: Qwen 返回的文本内容。planner.py 会继续解析其中的 JSON。
    """
    logger.info("Calling Qwen API: model=%s, web_search=True", QWEN_MODEL)

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.2,
        extra_body={
            "enable_search": True
        },
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError("Qwen API 返回内容为空")

    logger.info("Qwen API response received successfully")
    return content


def generate_travel_plan(user_request, candidates):
    """
    保留旧版 planner.py 的兼容接口。
    新版 planner.py 主要使用 call_qwen_api(prompt)。
    """
    prompt = f"""
你是 Personal Guide 个性化旅行规划智能体。

【用户需求】
{json.dumps(user_request, ensure_ascii=False, indent=2)}

【候选地点】
{json.dumps(candidates, ensure_ascii=False, indent=2)}

请结合联网搜索核验开放状态、天气、预约、票价和交通信息，
生成一日游行程。

只返回合法 JSON，不要使用 Markdown 代码块：

{{
  "final_itinerary": [
    {{
      "time": "09:00 - 11:00",
      "name": "地点名称",
      "type": "景点/餐饮/活动",
      "description": "简要说明",
      "location": "地点",
      "duration": "2小时",
      "price": "60元",
      "rating": 4.8,
      "tags": ["历史文化"],
      "reason": "推荐理由",
      "transport": "交通建议"
    }}
  ],
  "dynamic_info": "动态信息与时效性说明",
  "reasoning": "面向用户的推荐理由摘要"
}}
""".strip()

    return call_qwen_api(prompt)
