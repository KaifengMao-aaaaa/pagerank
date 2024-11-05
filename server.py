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
    cursor.execute("SELECT ROW_NUMBER() OVER (ORDER BY score DESC) AS rank, name, score, country FROM developers;")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    data = [{'rank': row[0], "name": row[1], "score": row[2], "country": row[3]} for row in rows]
    return jsonify(data)

# 启动服务器
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
