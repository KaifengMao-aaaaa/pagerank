import psycopg2
from pyspark.sql import SparkSession
from graphframes import GraphFrame
from pyspark.sql.types import StructType, StructField, StringType, FloatType
spark = SparkSession.builder \
    .appName("SaveNodesToHDFS") \
    .config("spark.hadoop.fs.defaultFS", "hdfs://localhost:9000") \
    .config("spark.jars.packages", "graphframes:graphframes:0.8.2-spark3.0-s_2.12") \
    .getOrCreate()
spark.sparkContext.setLogLevel("ERROR")
db_config = {
    'host': 'localhost',         
    'database': 'github',         
    'user': 'host',          
}
conn = psycopg2.connect(**db_config)


nodes_path = "hdfs:///data/nodes"
edges_path = "hdfs:///data/edges"
vertices_df = spark.read.json(nodes_path, multiLine=True)
edges_df = spark.read.json(edges_path, multiLine=True)
vertices_df.show()
edges_df.show()

g = GraphFrame(vertices_df, edges_df)

# 运行 PageRank 算法
results = g.pageRank(resetProbability=0.15, maxIter=10)
pagerank_df = results.vertices.selectExpr("id", "pagerank", "attributes.name as name") \
    .orderBy("pagerank", ascending=False) \
    .toPandas()
cur = conn.cursor()

# 更新每个节点的 PageRank 分数和 name
for index, row in pagerank_df.iterrows():
    node_id = row['id']
    pagerank_score = row['pagerank']
    name = row['name']
    # 插入或更新节点的 PageRank 分数和 name
    cur.execute("""
        UPDATE  developers set score = %s where name = %s
    """, (pagerank_score ,name))
    conn.commit()
cur.close()


# spark.stop()