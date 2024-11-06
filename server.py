from flask import Flask, jsonify, request
import psycopg2
from flask_cors import CORS
from dotenv import load_dotenv
import os
from openai import OpenAI
# 加载 .env 文件
load_dotenv()
app = Flask(__name__)
CORS(app)

# PostgreSQL 数据库配置
db_config = {
    'host': os.getenv("DB_HOST"),
    'database': os.getenv("DB_DATABASE"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD")
}

@app.route('/')
def home():
    return "Welcome to the Leaderboard!"

# 定义一个 API 路由
@app.route('/api/data', methods=['GET'])
def get_data():
    # 连接到数据库
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()

    # 获取请求参数
    specialty = request.args.get('specialty') 
    country = request.args.get('country') 
    # 根据 specialty 和 country 参数决定查询条件
    query = """
        SELECT rank, d.name, score, country, country_trust, r.name as specialty
        FROM developer_rankings d
        JOIN research_view r ON r.developer_name = d.name
        WHERE 1=1
    """
    params = []

    if specialty:
        query += " AND r.name = %s"
        params.append(specialty)

    if country:
        query += " AND d.country = %s"
        params.append(country)

    cursor.execute(query, tuple(params))

    # 创建一个字典以便按开发者名称聚合 specialties
    data_dict = {}
    rows = cursor.fetchall()
    for row in rows:
        rank, name, score, country, country_trust, specialty = row
        if name not in data_dict:
            data_dict[name] = {
                'rank': rank,
                'name': name,
                'score': score,
                'country': country,
                'specialty': [specialty],  # 初始化为列表
                'country_trust': country_trust
            }
        else:
            data_dict[name]['specialty'].append(specialty)  # 添加 specialty

    # 将字典转换为列表格式
    data = list(data_dict.values())

    # 关闭数据库连接
    cursor.close()
    conn.close()

    # 返回 JSON 数据
    return jsonify(data)

client = OpenAI(
   # 设置 OpenAI API 密钥
    api_key=os.getenv("OPENAI_API_KEY"),
)
# API 端点：获取开发者详细信息
@app.route('/api/dev_info', methods=['GET'])
def get_developer_info():
    username = request.args.get('username')
    
    if not username:
        return jsonify({"error": "Username is required"}), 400

    try:
        chat_completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
            {"role": "system", "content": "You are a helpful assistant that formats data."},
            {"role": "user", "content": f"根据用户{username}github上面的信息整理一下，给我一个html格式给我，不需要任何其他的解释。必须包含头像，名字，最近仓库(需要总结一下这个仓库列出来star和watch数据加上链接)和个人博客(包含链接)，使用中文，如果这个人个人介绍有重要内容，也可以翻译成中文列出来。最外面不要有```html"}
            ]
        )
        response_dict = chat_completion.to_dict() if hasattr(chat_completion, 'to_dict') else dict(chat_completion)

        # 返回 JSON 格式的响应
        return jsonify(response_dict['choices'][0]['message']['content']), 200
    
    except Exception as e:  # 捕获所有异常
        return jsonify({"error": str(e)}), 500

# 启动服务器
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
