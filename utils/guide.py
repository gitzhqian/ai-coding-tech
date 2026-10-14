# -*- coding: utf-8 -*-
"""
景点历史解说技能（Attraction History Commentary Skill）

为 Personal Guide 智能导游提供“景点历史解说”能力：
根据景点名称、城市、类型、简介等信息，调用 Qwen 生成
历史沿革、趣味典故、必看亮点与游览贴士，供行程中随时查看 / 收听。

对外主要接口：
    generate_attraction_history(name, city, type_, description, tags)
"""
import json
import re
from datetime import datetime

try:
    from . import ai_client
except ImportError:  # 兼容直接以 utils.xxx 方式导入
    import utils.ai_client as ai_client


SYSTEM_PROMPT = "你是一位知识渊博、讲解生动的资深导游，擅长讲述景点背后的历史与故事。"


# =========================
# 通用工具
# =========================

def _normalize_tags(tags):
    if not tags:
        return []
    if isinstance(tags, str):
        return [x.strip() for x in re.split(r"[,，、;；]", tags) if x.strip()]
    return [str(x).strip() for x in tags if str(x).strip()]


def _extract_json_payload(raw_response):
    """兼容 Qwen 返回：dict / 纯 JSON / ```json 包裹 / 夹杂解释文字。"""
    if isinstance(raw_response, dict):
        return raw_response

    if raw_response is None:
        raise ValueError("Qwen API 返回为空")

    text = str(raw_response).strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _as_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value).strip()]


# =========================
# Prompt 构建
# =========================

def _build_history_prompt(name, city, type_, description, tags):
    tag_text = "、".join(tags) if tags else "无"
    return f"""
你是 Personal Guide 的“景点历史解说员”，擅长把景点背后的历史讲得生动、准确、有画面感。

请根据下面的景点信息，生成一份面向游客的景点历史解说。

【景点信息】
名称：{name}
城市：{city or '未提供'}
类型：{type_ or '未提供'}
简介：{description or '未提供'}
标签：{tag_text}

请综合运用你的知识，必要时结合联网搜索结果，确保史实准确。

请只返回合法 JSON，不要使用 Markdown 代码块：

{{
  "title": "景点名称",
  "history": "历史沿革与背景，200~400字，按时间脉络讲述",
  "stories": ["趣味典故或传说，1~3条"],
  "highlights": ["必看亮点，2~4条"],
  "tips": ["游览小贴士，1~3条"]
}}

要求：
1. 内容准确，对说法不一或难以考证的内容要注明“说法不一 / 有待考证”；
2. 语气生动，适合作为导游口播解说稿；
3. 不要编造具体的年代、人物之外的虚假细节；
4. 只返回 JSON，不要输出多余文字。
""".strip()


# =========================
# 本地兜底
# =========================

def _fallback_history(name, city, type_, description, tags, error_message=""):
    location = city or "当地"
    kind = type_ or "景点"
    base_desc = description or "暂无更多简介资料。"

    history = (
        f"{name}是{location}具有代表性的{kind}。{base_desc} "
        "关于它更完整的历史沿革与典故，建议出行前查阅权威资料进一步了解。"
    )

    return {
        "title": name,
        "history": history,
        "stories": [],
        "highlights": tags or ["可结合现场导览深入了解该处历史"],
        "tips": ["目前为本地解说模式，联网生成内容暂时不可用。"],
        "_fallback": True,
        "_error": error_message,
    }


# =========================
# 主入口
# =========================

def generate_attraction_history(name, city="", type_="", description="", tags=None):
    """
    生成景点历史解说。

    返回 dict：
        {
            "name": 景点名称,
            "city": 城市,
            "title": 标题,
            "history": 历史沿革（文本）,
            "stories": [趣味典故...],
            "highlights": [必看亮点...],
            "tips": [游览贴士...],
            "qwen_used": bool,
            "generated_at": "YYYY-MM-DD HH:MM:SS",
        }

    优先调用 Qwen 生成；调用失败时回退为本地兜底解说，保证接口始终可用。
    """
    name = (name or "").strip()
    city = (city or "").strip()
    type_ = (type_ or "").strip()
    description = (description or "").strip()
    tags = _normalize_tags(tags)

    if not name:
        raise ValueError("景点名称不能为空")

    fallback_error = ""

    try:
        if not hasattr(ai_client, "call_qwen_api"):
            raise AttributeError("utils.ai_client 中未找到 call_qwen_api")

        prompt = _build_history_prompt(name, city, type_, description, tags)
        raw = ai_client.call_qwen_api(prompt, system_prompt=SYSTEM_PROMPT)
        payload = _extract_json_payload(raw)

        history = str(payload.get("history", "")).strip()
        if not history:
            raise ValueError("Qwen 返回的解说内容为空")

        return {
            "name": name,
            "city": city,
            "title": str(payload.get("title", name)).strip() or name,
            "history": history,
            "stories": _as_list(payload.get("stories")),
            "highlights": _as_list(payload.get("highlights")),
            "tips": _as_list(payload.get("tips")),
            "qwen_used": True,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    except Exception as exc:  # noqa: BLE001 - 兜底保证功能可用
        fallback_error = str(exc)

    result = _fallback_history(name, city, type_, description, tags, fallback_error)
    result.update({
        "name": name,
        "city": city,
        "qwen_used": False,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    return result
