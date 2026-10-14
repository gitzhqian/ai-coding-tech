from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)

from utils.planner import generate_personalized_itinerary
from utils.guide import generate_attraction_history

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_itinerary():
    city = request.form.get('city', '').strip()
    travel_date = request.form.get('date', '')
    start_time = request.form.get('start_time', '09:00')
    end_time = request.form.get('end_time', '18:00')
    budget = request.form.get('budget', '500')
    interests = request.form.getlist('interests')
    food_preferences = request.form.get('food_preference', '')
    transportation = request.form.get('transportation', '步行')
    travel_pace = request.form.get('travel_pace', '适中')

    if not city or not travel_date:
        return render_template('index.html', error='城市和旅行日期是必填项')

    try:
        with open('data/attractions.json', 'r', encoding='utf-8') as f:
            attractions_data = json.load(f)
    except FileNotFoundError:
        return render_template('index.html', error='找不到景点数据文件')
    except json.JSONDecodeError:
        return render_template('index.html', error='景点数据格式错误')

    try:
        itinerary = generate_personalized_itinerary(
            city=city,
            date=travel_date,
            start_time=start_time,
            end_time=end_time,
            budget=budget,
            interests=interests,
            food_preferences=food_preferences,
            transportation=transportation,
            travel_pace=travel_pace,
            attractions_data=attractions_data
        )
        return render_template('result.html', itinerary=itinerary, city=city, date=travel_date)
    except Exception as e:
        logging.error(f"Error generating itinerary: {e}", exc_info=True)
        return render_template('index.html', error=f'生成行程时出错: {str(e)}')

@app.route('/commentary', methods=['POST'])
def generate_commentary():
    """景点历史解说技能：根据景点信息生成历史解说，返回 JSON。"""
    payload = request.get_json(silent=True) or request.form
    name = (payload.get('name') or '').strip()

    if not name:
        return jsonify({'error': '缺少景点名称'}), 400

    try:
        commentary = generate_attraction_history(
            name=name,
            city=(payload.get('city') or '').strip(),
            type_=(payload.get('type') or '').strip(),
            description=(payload.get('description') or '').strip(),
            tags=payload.get('tags') or [],
        )
        return jsonify(commentary)
    except Exception as e:
        logging.error(f"Error generating commentary: {e}", exc_info=True)
        return jsonify({'error': f'生成历史解说时出错: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
