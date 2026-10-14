import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    # Qwen API 配置
    QWEN_API_KEY = os.getenv('QWEN_API_KEY', '')
    QWEN_BASE_URL = os.getenv('QWEN_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
    
    # 应用配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    
    # 数据文件路径
    ATTRACTIONS_FILE = 'data/attractions.json'
    CITY_INFO_FILE = 'data/city_info.json'