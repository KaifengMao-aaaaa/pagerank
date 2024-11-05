from flask import Flask, jsonify, request
import psycopg2
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
db_config = {
    'host': 'localhost',   
    'database': 'github',  
    'user': 'host',       
}
@app.route('/')
def home():
    return "Welcome to the Leaderboard!"

# 定义一个 API 路由
@app.route('/api/data', methods=['GET'])
def get_data():
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    specialty = request.args.get('specialty') 
    if specialty:
        cursor.execute("""
            SELECT rank, d.name, score, country, r.name as specialty
            FROM developer_rankings d
            join research_view r
            on r.developer_name = d.name
            WHERE r.name = %s;
        """, (specialty,))
    else:
        cursor.execute("""
            SELECT rank, d.name, score, country, r.name as specialty
            FROM developer_rankings d
            join research_view r
            on r.developer_name = d.name;
        """)
    # 创建一个字典以便按开发者名称聚合 specialties
    data_dict = {}
    rows = cursor.fetchall()
    for row in rows:
        rank, name, score, country, specialty = row
        if name not in data_dict:
            data_dict[name] = {
                'rank': rank,
                'name': name,
                'score': score,
                'country': country,
                'specialty': [specialty]  # 初始化为列表
            }
        else:
            data_dict[name]['specialty'].append(specialty)  # 添加 specialty

    # 将字典转换为列表格式
    data = list(data_dict.values())
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(data)

# 启动服务器
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
