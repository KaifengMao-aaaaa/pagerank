#!/bin/bash
hdfs dfs -rm -r /data
# 创建 HDFS 目录结构
hdfs dfs -mkdir -p /data/metadata
echo "1" | hdfs dfs -put - '/data/metadata/history' 
hdfs dfs -mkdir -p /data/edges
hdfs dfs -mkdir -p /data/nodes
# 检查是否成功创建
if [ $? -eq 0 ]; then
    echo "HDFS structure initialized successfully."
else
    echo "Failed to initialize HDFS structure."
fi