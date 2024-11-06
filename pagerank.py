import psycopg2
from pyspark.sql import SparkSession
from graphframes import GraphFrame
from pyspark.sql.types import StructType, StructField, StringType, FloatType
from dotenv import load_dotenv
import os
# 加载 .env 文件
load_dotenv()
# 创建 SparkSession，配置 HDFS 和 GraphFrames 包
spark = SparkSession.builder \
    .appName("SaveNodesToHDFS") \
    .config("spark.hadoop.fs.defaultFS", "hdfs://localhost:9000") \
    .config("spark.jars.packages", "graphframes:graphframes:0.8.2-spark3.0-s_2.12") \
    .getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

# PostgreSQL 数据库配置
db_config = {
    'host': os.getenv("DB_HOST"),
    'database': os.getenv("DB_DATABASE"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD")
}
conn = psycopg2.connect(**db_config)

# 设置数据路径
nodes_path = "hdfs:///data/nodes"
edges_path = "hdfs:///data/edges"

# 从 HDFS 加载顶点和边数据
vertices_df = spark.read.json(nodes_path, multiLine=True)
edges_df = spark.read.json(edges_path, multiLine=True)

# 显示数据（调试用）
vertices_df.show()
edges_df.show()

# 构建图结构
g = GraphFrame(vertices_df, edges_df)

# 运行 PageRank 算法
results = g.pageRank(resetProbability=0.15, maxIter=10)

# 提取 PageRank 结果，并按分数降序排序
pagerank_df = results.vertices.selectExpr("id", "pagerank", "attributes.name as name")

# 创建游标用于更新 PostgreSQL 数据库
cur = conn.cursor()

# 更新每个节点的 PageRank 分数和名称
for row in pagerank_df.collect():  # 使用 collect 将 Spark DataFrame 转换为行对象列表
    node_id = row['id']
    pagerank_score = row['pagerank']
    name = row['name']
    
    # 插入或更新节点的 PageRank 分数和名称
    cur.execute("""
        UPDATE developers SET score = %s WHERE name = %s
    """, (pagerank_score, name))
    conn.commit()

# 关闭游标和数据库连接
cur.close()
conn.close()

# 停止 SparkSession
spark.stop()
