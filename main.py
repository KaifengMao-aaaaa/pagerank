import psycopg2
from psycopg2 import sql

# 连接数据库
try:
    conn = psycopg2.connect(
        host="localhost",       # 数据库主机地址
        database="github",      # 数据库名称
        user="host",       # 用户名
    )
    print("Connected to the database successfully.")
    
    # 创建一个游标对象
    cursor = conn.cursor()

    # 执行一个查询
    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()
    print("Database version:", db_version)

    cursor.close()
    conn.close()
    print("Database connection closed.")
except Exception as e:
    print("Error connecting to the database:", e)
