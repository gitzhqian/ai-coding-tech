import json
import random
import re
from datetime import datetime, timedelta

try:
    from . import ai_client
except ImportError:
    import utils.ai_client as ai_client


# =========================
# 通用工具
# =========================

def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_interests(interests):
    if not interests:
        return []
    if isinstance(interests, str):
        return [x.strip() for x in re.split(r"[,，、;；]", interests) if x.strip()]
    return [str(x).strip() for x in interests if str(x).strip()]


def _available_hours(start_time, end_time, default=8.0):
    try:
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        if end <= start:
            return default
        return (end - start).total_seconds() / 3600
    except (TypeError, ValueError):
        return default


def _extract_json_payload(raw_response):
    """
    兼容以下 Qwen 返回：
    1. dict
    2. 纯 JSON 字符串
    3. ```json ... ``` 包裹的 JSON
    4. 前后夹杂少量解释文字的 JSON
    """
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


def _call_qwen_prompt(prompt):
    """
    统一通过 ai_client 调用 Qwen。
    推荐 ai_client.py 暴露：
        call_qwen_api(prompt)

    如果项目仍使用 generate_travel_plan(user_request, candidates)，
    则最终行程阶段会兼容；候选搜索阶段必须有 call_qwen_api。
    """
    if hasattr(ai_client, "call_qwen_api"):
        return ai_client.call_qwen_api(prompt)

    raise AttributeError(
        "utils.ai_client 中未找到 call_qwen_api(prompt)。"
        "请在 ai_client.py 中保留该接口，并确保其中启用了 enable_search=True。"
    )


# =========================
# 本地候选筛选
# =========================

def _candidate_score(attraction, interests, budget_limit):
    """
    简单、可解释的候选评分：
    - 兴趣匹配
    - 预算友好
    - 景点评分
    """
    score = 0.0
    tags = [str(tag).lower() for tag in attraction.get("tags", [])]

    for interest in interests:
        needle = interest.lower()
        if any(needle in tag or tag in needle for tag in tags):
            score += 4.0

    price = _to_float(
        attraction.get("price", attraction.get("estimated_price", 0)),
        0.0
    )
    if budget_limit > 0 and price <= budget_limit * 0.30:
        score += 2.0

    rating = _to_float(attraction.get("rating"), 0.0)
    if rating > 0:
        score += min(rating / 5.0 * 2.0, 2.0)

    return score


def _select_local_candidates(city, budget, interests, travel_pace, attractions_data):
    """
    从 attractions.json 中寻找当前城市候选景点。
    注意：没有当前城市数据时返回 []，不随机推荐其他城市景点。
    """
    interests = _normalize_interests(interests)
    budget_limit = _to_float(budget, 500.0)

    city_attractions = [
        attr for attr in attractions_data
        if str(attr.get("city", "")).strip() == str(city).strip()
    ]

    if not city_attractions:
        return []

    affordable = [
        attr for attr in city_attractions
        if _to_float(attr.get("price"), 0.0) <= budget_limit
    ]
    pool = affordable or city_attractions

    ranked = sorted(
        pool,
        key=lambda attr: _candidate_score(attr, interests, budget_limit),
        reverse=True,
    )

    max_candidates = {
        "慢": 3,
        "轻松": 3,
        "适中": 5,
        "快": 6,
        "紧凑": 6,
    }.get(str(travel_pace).strip(), 5)

    return ranked[:max_candidates]


# =========================
# 第一阶段：Qwen 动态候选生成
# =========================

def _build_candidate_search_prompt(user_request):
    return f"""
你是 Personal Guide 的“旅行候选数据检索器”。

当前本地 attractions.json 中没有找到足够的目标城市景点数据。
请使用联网搜索，为下面的用户需求检索 5~8 个真实、适合的一日游候选地点。

【用户需求】
{json.dumps(user_request, ensure_ascii=False, indent=2)}

请综合考虑：
1. 目的城市；
2. 旅行日期；
3. 兴趣偏好；
4. 用户预算；
5. 交通方式；
6. 旅行节奏；
7. 景点之间的大致地理合理性；
8. 景点开放状态、票价、预约、天气等可能变化的信息。

请只返回合法 JSON，不要使用 Markdown 代码块：

{{
  "candidates": [
    {{
      "name": "真实地点名称",
      "city": "{user_request.get('city', '')}",
      "type": "历史文化/博物馆/公园/美食/建筑等",
      "description": "简要说明",
      "location": "所在区域或地址",
      "duration": 2,
      "price": 0,
      "rating": 4.5,
      "tags": ["历史文化", "建筑"],
      "reason": "为什么适合该用户",
      "source_note": "动态检索信息说明"
    }}
  ],
  "dynamic_info": "本次候选检索涉及的开放时间、天气、预约、票价等动态信息摘要"
}}

要求：
- 只能返回真实存在的地点；
- 无法确认的实时信息要明确标注“需出行前确认”；
- duration 使用小时数；
- price 使用人民币估算值；
- 不要因为没有本地 JSON 数据而返回空列表。
""".strip()


def _search_dynamic_candidates(user_request):
    """
    当本地没有目标城市数据时，调用 Qwen 联网搜索动态候选。
    """
    prompt = _build_candidate_search_prompt(user_request)
    raw = _call_qwen_prompt(prompt)
    payload = _extract_json_payload(raw)

    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("Qwen 候选检索返回的 candidates 不是列表")

    # 仅保留基本合法的候选项
    cleaned = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        if not item.get("name"):
            continue

        cleaned.append({
            "name": item.get("name", ""),
            "city": item.get("city", user_request.get("city", "")),
            "type": item.get("type", "景点"),
            "description": item.get("description", ""),
            "location": item.get("location", ""),
            "duration": _to_float(
                item.get("duration", item.get("estimated_duration", 1.5)),
                1.5
            ),
            "price": _to_float(
                item.get("price", item.get("estimated_price", 0)),
                0.0
            ),
            "rating": _to_float(item.get("rating"), 0.0),
            "tags": item.get("tags", []),
            "reason": item.get("reason", ""),
            "source_note": item.get("source_note", ""),
        })

    if not cleaned:
        raise ValueError("Qwen 联网搜索未返回有效候选地点")

    return cleaned, payload.get("dynamic_info", "")


# =========================
# 第二阶段：Qwen 行程规划
# =========================

def _build_itinerary_prompt(user_request, candidates, candidate_source, candidate_dynamic_info=""):
    return f"""
你是 Personal Guide 的“个性化旅行规划智能体”。

请根据用户需求与候选地点，生成真正可执行的一日游路线。

【用户需求】
{json.dumps(user_request, ensure_ascii=False, indent=2)}

【候选地点来源】
{candidate_source}

【候选地点】
{json.dumps(candidates, ensure_ascii=False, indent=2)}

【候选阶段动态信息】
{candidate_dynamic_info or "无"}

你可以继续使用联网搜索核验：
- 景点开放情况；
- 临时闭馆或预约要求；
- 票价变化；
- 天气适宜性；
- 交通与步行合理性；
- 当前旅行注意事项。

请只返回合法 JSON，不要使用 Markdown 代码块：

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
      "transport": "与上一站之间的交通建议"
    }}
  ],
  "dynamic_info": "天气、开放状态、预约、交通等动态信息，以及需出行前再次确认的内容",
  "reasoning": "简要、面向用户说明推荐逻辑，不要输出内部思维过程",
  "estimated_total_cost": "预计总费用"
}}

要求：
1. 不超过用户给出的开始/结束时间；
2. 尽量不超过预算；
3. 优先满足兴趣与饮食偏好；
4. 交通方式必须符合用户选择；
5. “轻松/慢”节奏减少地点，“快/紧凑”可适当增加；
6. 路线应尽可能减少无意义折返；
7. 餐饮可以作为行程中的一个 item；
8. 对未来日期的开放时间、天气、票价等不得假装已确定，必须注明时效性。
""".strip()


def _generate_qwen_itinerary(
    user_request,
    candidates,
    candidate_source,
    candidate_dynamic_info=""
):
    """
    优先走 call_qwen_api(prompt)。
    如 ai_client 仍暴露 generate_travel_plan，也可作为兼容分支。
    """
    if hasattr(ai_client, "call_qwen_api"):
        prompt = _build_itinerary_prompt(
            user_request,
            candidates,
            candidate_source,
            candidate_dynamic_info,
        )
        return ai_client.call_qwen_api(prompt)

    if hasattr(ai_client, "generate_travel_plan"):
        return ai_client.generate_travel_plan(user_request, candidates)

    raise AttributeError(
        "utils.ai_client 中未找到 call_qwen_api 或 generate_travel_plan"
    )


# =========================
# 本地兜底
# =========================

def generate_food_recommendation(food_preferences, city):
    recommendations = [
        f"可在{city}品尝当地特色小吃",
        f"可选择{city}口碑较好的本地餐厅享用正餐",
        f"可根据行程所在区域就近体验{city}地方风味",
    ]

    suggestion = random.choice(recommendations)
    if food_preferences:
        return f"根据您的饮食偏好（{food_preferences}），{suggestion}"
    return suggestion


def generate_itinerary_summary(
    city,
    date,
    start_time,
    end_time,
    budget,
    interests,
    transportation,
    travel_pace,
    selected_attractions,
):
    total_cost = sum(
        _to_float(attr.get("price"), 0.0)
        for attr in selected_attractions
    )
    total_duration = sum(
        _to_float(attr.get("duration"), 0.0)
        for attr in selected_attractions
    )
    interests = _normalize_interests(interests)

    lines = [
        "个性化行程概览:",
        f"- 目的地: {city}",
        f"- 旅行日期: {date}",
        f"- 行程时间: {start_time} - {end_time}",
        f"- 预算范围: {budget}元",
        f"- 旅行节奏: {travel_pace}",
        f"- 交通方式: {transportation}",
        f"- 候选地点数量: {len(selected_attractions)}",
        f"- 候选预计总耗时: {total_duration:g}小时",
        f"- 候选预计总费用: {total_cost:g}元",
    ]

    if interests:
        lines.append(f"- 兴趣偏好: {', '.join(interests)}")

    return "\n".join(lines)


def _build_local_fallback(
    city,
    date,
    start_time,
    end_time,
    budget,
    interests,
    food_preferences,
    transportation,
    travel_pace,
    selected_attractions,
    error_message,
    candidate_source,
):
    """
    Qwen 最终规划失败时，本地兜底。
    """
    available_hours = _available_hours(start_time, end_time)
    budget_limit = _to_float(budget, 500.0)

    itinerary_items = []
    current_time = datetime.strptime(start_time, "%H:%M")
    used_hours = 0.0
    used_cost = 0.0

    for attraction in selected_attractions:
        duration = _to_float(attraction.get("duration"), 1.0)
        price = _to_float(attraction.get("price"), 0.0)

        if used_hours + duration > available_hours:
            continue
        if budget_limit > 0 and used_cost + price > budget_limit:
            continue

        item_start = current_time
        item_end = item_start + timedelta(hours=duration)

        itinerary_items.append({
            "time": f"{item_start.strftime('%H:%M')} - {item_end.strftime('%H:%M')}",
            "name": attraction.get("name", "未命名地点"),
            "type": attraction.get("type", "景点"),
            "description": attraction.get("description", ""),
            "location": attraction.get("location", ""),
            "duration": f"{duration:g}小时",
            "price": f"{price:g}元",
            "rating": attraction.get("rating", ""),
            "tags": attraction.get("tags", []),
            "reason": attraction.get("reason", "根据候选数据与用户约束筛选"),
            "transport": transportation,
        })

        current_time = item_end
        used_hours += duration
        used_cost += price

    return {
        "summary": generate_itinerary_summary(
            city,
            date,
            start_time,
            end_time,
            budget,
            interests,
            transportation,
            travel_pace,
            selected_attractions,
        ),
        "local_candidates": selected_attractions,
        "final_itinerary": itinerary_items,
        "dynamic_info": (
            f"Qwen 最终规划调用失败，当前结果由本地规则根据“{candidate_source}”候选生成。"
        ),
        "reasoning": f"已启用本地兜底模式。错误：{error_message}",
        "food_recommendation": generate_food_recommendation(
            food_preferences,
            city
        ),
        "total_budget": f"{budget}元",
        "transportation": transportation,
        "travel_pace": travel_pace,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "qwen_used": False,
        "candidate_source": candidate_source,
    }


# =========================
# 主入口
# =========================

def generate_personalized_itinerary(
    city,
    date,
    start_time,
    end_time,
    budget,
    interests,
    food_preferences,
    transportation,
    travel_pace,
    attractions_data,
):
    """
    Personal Guide 两阶段智能推荐流程：

    1. 本地 attractions.json 中有目标城市数据：
       本地筛选 -> Top-K 候选

    2. 本地没有目标城市数据：
       Qwen 联网搜索 -> 动态候选

    3. 将候选 + 用户约束再次交给 Qwen：
       生成最终个性化行程

    4. Qwen 最终调用失败：
       本地规则兜底
    """
    interests = _normalize_interests(interests)

    user_request = {
        "city": city,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "budget": budget,
        "interests": interests,
        "food_preferences": food_preferences,
        "transportation": transportation,
        "travel_pace": travel_pace,
    }

    # -------- 第一阶段：候选生成 --------
    selected_attractions = _select_local_candidates(
        city=city,
        budget=budget,
        interests=interests,
        travel_pace=travel_pace,
        attractions_data=attractions_data,
    )

    candidate_dynamic_info = ""

    if selected_attractions:
        candidate_source = "本地 attractions.json + 本地评分算法"
    else:
        candidate_source = "Qwen 联网搜索"
        try:
            selected_attractions, candidate_dynamic_info = _search_dynamic_candidates(
                user_request
            )
        except Exception as exc:
            # 候选阶段就失败时，不能伪造其它城市数据。
            return {
                "summary": generate_itinerary_summary(
                    city,
                    date,
                    start_time,
                    end_time,
                    budget,
                    interests,
                    transportation,
                    travel_pace,
                    [],
                ),
                "local_candidates": [],
                "final_itinerary": [],
                "dynamic_info": (
                    f"本地没有“{city}”候选景点，且 Qwen 联网候选检索失败。"
                ),
                "reasoning": f"候选生成失败：{exc}",
                "food_recommendation": generate_food_recommendation(
                    food_preferences,
                    city
                ),
                "total_budget": f"{budget}元",
                "transportation": transportation,
                "travel_pace": travel_pace,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "qwen_used": False,
                "candidate_source": "无有效候选数据",
            }

    # 对动态候选也做一次本地可解释排序
    ranked_candidates = sorted(
        selected_attractions,
        key=lambda attr: _candidate_score(
            attr,
            interests,
            _to_float(budget, 500.0)
        ),
        reverse=True,
    )

    # 第二阶段最多给 Qwen 8 个候选，避免 Prompt 过长
    ranked_candidates = ranked_candidates[:8]

    # -------- 第二阶段：最终行程规划 --------
    try:
        raw_response = _generate_qwen_itinerary(
            user_request=user_request,
            candidates=ranked_candidates,
            candidate_source=candidate_source,
            candidate_dynamic_info=candidate_dynamic_info,
        )

        response_data = _extract_json_payload(raw_response)

        final_itinerary = response_data.get("final_itinerary", [])
        if not isinstance(final_itinerary, list):
            raise ValueError("Qwen 返回的 final_itinerary 不是列表")

        if not final_itinerary:
            raise ValueError("Qwen 返回的 final_itinerary 为空")

        dynamic_info = response_data.get("dynamic_info", "")
        if candidate_dynamic_info:
            dynamic_info = (
                f"{candidate_dynamic_info}\n\n"
                f"最终规划动态信息：{dynamic_info}"
            ).strip()

        return {
            "summary": generate_itinerary_summary(
                city,
                date,
                start_time,
                end_time,
                budget,
                interests,
                transportation,
                travel_pace,
                ranked_candidates,
            ),
            "local_candidates": ranked_candidates,
            "final_itinerary": final_itinerary,
            "dynamic_info": dynamic_info,
            "reasoning": response_data.get("reasoning", ""),
            "food_recommendation": generate_food_recommendation(
                food_preferences,
                city
            ),
            "total_budget": response_data.get(
                "estimated_total_cost",
                f"{budget}元"
            ),
            "transportation": transportation,
            "travel_pace": travel_pace,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "qwen_used": True,
            "candidate_source": candidate_source,
        }

    except Exception as exc:
        return _build_local_fallback(
            city=city,
            date=date,
            start_time=start_time,
            end_time=end_time,
            budget=budget,
            interests=interests,
            food_preferences=food_preferences,
            transportation=transportation,
            travel_pace=travel_pace,
            selected_attractions=ranked_candidates,
            error_message=str(exc),
            candidate_source=candidate_source,
        )
