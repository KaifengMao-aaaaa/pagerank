from collections import defaultdict
import os
import json

def load_from_folder(folder_path):
    nodes = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path): 
            with open(file_path, "r") as f:
                node_data = json.load(f)
                nodes.append(node_data) 
    return nodes
def calculate_edge_counts():
    # 使用 defaultdict 初始化出边和入边计数字典
    out_count = defaultdict(int)
    in_count = defaultdict(int)
    # 遍历 edges，更新出边和入边计数
    for edge in load_from_folder('data/edges'):
        out_count[edge["src"]] += 1  # 出边
        in_count[edge["dst"]] += 1   # 入边
    # 整合每个节点的计数结果
    node_stats = []
    for node in load_from_folder('data/nodes'):
        node_id = node["id"]
        stats = {
            "id": node_id,
            "outgoing_edges": out_count[node_id],
            "incoming_edges": in_count[node_id],
        }
        node_stats.append(stats)

    return node_stats

# 运行并打印统计结果
node_statistics = calculate_edge_counts()
for stats in node_statistics:
    print(f"Node {stats['id']}: Outgoing edges = {stats['outgoing_edges']}, Incoming edges = {stats['incoming_edges']}")
