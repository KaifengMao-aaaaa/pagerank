# 导入库
import psycopg2
import tempfile
import sys
import requests
from dotenv import load_dotenv
import os
import subprocess
from collections import Counter
import json
from datetime import datetime
import threading
import time
from datetime import datetime, timedelta
# import schedule  # 如需要定时任务可启用
import time
import spacy

# 加载 .env 文件
load_dotenv()

# 加载 spaCy 预训练模型
nlp = spacy.load("en_core_web_sm")

# 数据库配置
db_config = {
    'host': os.getenv("DB_HOST"),
    'database': os.getenv("DB_DATABASE"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD")
}

# 连接 PostgreSQL 数据库
try:
    conn = psycopg2.connect(**db_config)
except Exception as e:
    print(f"数据库连接错误: {e}")

# GitHub API 配置
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_HEADERS = {
    "Authorization": os.getenv("GITHUB_TOKEN"),
    "User-Agent": os.getenv("USER_AGENT")
}

# HDFS 路径配置
HDFS_NODES_PATH = "hdfs:///data/nodes"
HDFS_EDGES_PATH = "hdfs:///data/edges"
HDFS_META_PATH = "hdfs:///data/metadata"

# 配置常量
DEVELOPER_ID = 1
DEVELOPER_PAGING_LIMIT = 3
PR_LIMIT = 10
RATE_START = 5000
DEVELOPER_NUM = 0
def fetch_developers_data():
    """获取多个开发者的节点和相关的边"""
    global DEVELOPER_ID, DEVELOPER_NUM
    developer_url = f"{GITHUB_API_BASE_URL}/users?since={DEVELOPER_ID}&per_page={DEVELOPER_PAGING_LIMIT}"
    response = requests.get(developer_url, headers=GITHUB_HEADERS)
    nodes = []
    edges = []
    last_developer = DEVELOPER_ID
    if response.status_code == 200:
        developers_data = response.json()
        for developer in developers_data:
            developer_info = generate_developer_graph_data(developer['login'], developer['node_id'])
            edges.extend(developer_info['edges'])
            nodes.extend(developer_info['node'])
            print(f"获取到了用户{developer['login']}的相关信息")
            DEVELOPER_NUM += 1
            last_developer = developer['id']
    DEVELOPER_NUM += DEVELOPER_PAGING_LIMIT
    DEVELOPER_ID = last_developer
    return [nodes, edges]

def guess_position(text):
    """获取文本中的位置信息"""
    doc = nlp(text)
    # 提取地理位置
    for ent in doc.ents:
        if ent.label_ == "GPE": 
            return ent
def get_country_from_location(text):
    """通过文本猜测地址"""
    if text == None:
        return None
    location = guess_position(text)
    url = f'https://nominatim.openstreetmap.org/search?q={location}&format=json&addressdetails=1'
    time.sleep(1)
    response = requests.get(url, headers=GITHUB_HEADERS)
    data = response.json()
    if data:
        first_result = data[0]
        # 提取国家信息
        if 'address' in first_result and 'country' in first_result['address']:
            return first_result['address']['country']
        return None
    return None
def get_followers_locations(username):
    """获取开发者的大多数的关注对象的地理位置信息"""
    followers_locations = []
    
    url = f'https://api.github.com/users/{username}/following?per_page=10'
    response = requests.get(url, headers=GITHUB_HEADERS)
    followers = response.json()
    for follower in followers:
        follower_location = get_developer_location(follower['login'])
        followers_locations.append(follower_location)
    location_counter = Counter(followers_locations)
    most_common_location = location_counter.most_common(1)
    if most_common_location:
        location, count = most_common_location[0]
        frequency = (count / len(followers_locations)) * 100 
    else:
        location, frequency = None, 0

    return location, frequency

def get_developer_location(username):
    """获取开发者的地理位置信息"""
    url = f'https://api.github.com/users/{username}'
    response = requests.get(url, headers=GITHUB_HEADERS)
    if response.status_code == 200:
        data = response.json()
        return get_country_from_location(data.get('location'))
    return None

def infer_country_for_developer(developer_name):
    """推断开发者的国家信息并返回可信度评分"""
    developer_country = get_developer_location(developer_name)
    probable_country, confidence = get_followers_locations(developer_name)
    if developer_country and developer_country == probable_country:
        return [developer_country, min(100, confidence + 50)]
    elif developer_country and developer_country != probable_country:
        return [developer_country, 60]
    elif not developer_country and probable_country:
        return [probable_country, min(100, confidence)]
    else:
        return [None, 0]

def fetch_repository_info(repository_url):
    """获取仓库的基本信息，包括名称、ID、节点ID、星标和话题"""
    response = requests.get(repository_url, headers=GITHUB_HEADERS)
    if response.status_code == 200:
        repo_data = response.json()
        return {
            'name': repo_data["name"],
            "id": repo_data["id"],
            'node_id': repo_data['node_id'],
            "stars": repo_data['stargazers_count'],
            "watchs": repo_data["subscribers_count"],
            "topics": repo_data["topics"]
        }
    return {}

def fetch_pull_request_contributions(pr_files_url):
    """计算并返回 PR 文件的总增加行数"""
    response = requests.get(pr_files_url, headers=GITHUB_HEADERS)
    if response.status_code == 200:
        pr_files = response.json()
        total_additions = sum(file["additions"] for file in pr_files)
        return total_additions
    return 0

def generate_developer_graph_data(developer_name, developer_node_id):
    """生成开发者的相关的节点和边信息，返回数据用于 PageRank 处理"""
    # 获取所有项目的 URLs
    search_url = f"{GITHUB_API_BASE_URL}/search/issues?q=type:pr+author:{developer_name}&per_page=100"
    response = requests.get(search_url, headers=GITHUB_HEADERS)
    
    repos = {}
    edges = []
    nodes = [{"id": developer_node_id, 'type': 'developer', 'attributes': {'name': developer_name}}]
    total_contribution = 1

    if response.status_code == 200:
        pr_data = response.json()
        pr_data = [pr for pr in pr_data['items'] if pr['pull_request']['merged_at'] is not None]

        for pr in pr_data[:PR_LIMIT]:
            repository_url = pr["repository_url"]
            pr_url = f"{repository_url}/pulls/{pr['number']}/files"
            
            # 获取项目节点和关联边
            repo_node = generate_repo_node_and_edges(repository_url, developer_name)
            nodes.append(repo_node['node'])
            
            # 过滤出与开发者相关的边
            filtered_edges = [edge for edge in repo_node['edges'] if edge['dst'] == developer_node_id]
            edges.extend(filtered_edges)

            # 获取贡献信息
            contribution = fetch_pull_request_contributions(pr_url)

            total_contribution += contribution
            repos[repo_node['node']['id']] = {"node_id": repo_node['node']['id'], "contribution": contribution}
    else:
        print(f"{search_url} 获取失败")
        sys.exit(1)
    # 根据贡献比例创建开发者到项目的边
    for repo in repos:
        edges.append({
            "src": developer_node_id,
            "dst": repos[repo]['node_id'],
            "weight": repos[repo]["contribution"] / total_contribution
        })
    # 推断开发者国家信息
    country = infer_country_for_developer(developer_name)
    # 保存到数据库
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO developers (name, score, country, country_trust)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO NOTHING
            """,
            (developer_name, 0, 'N/A' if country[0] is None else country[0], country[1])
        )
        conn.commit()
    return {"node": nodes, "edges": edges}

def db_insert_tags(topics, developer_name):
    with conn.cursor() as cur:
        for topic in topics:
            cur.execute(
                """
                INSERT INTO has_tag (name, developer_name, count)
                VALUES (%s, %s, 1)
                ON CONFLICT (name, developer_name)
                DO UPDATE SET count = has_tag.count + 1
                """,
                (topic , developer_name)
            )
        conn.commit()
def generate_repo_node_and_edges(repo_url, developer_name):
    """生成仓库的节点和边，返回数据用于 PageRank 处理"""
    basic_info = fetch_repository_info(repo_url)
    repo_pr_url = f"{repo_url}/pulls?state=all"
    response = requests.get(repo_pr_url, headers=GITHUB_HEADERS)
    
    contributors = {}
    total_additions = 1
    importance_base = basic_info['stars'] * 100 + basic_info['watchs'] + 1
    if response.status_code == 200:
        pr_data = response.json()
        for pr in pr_data:
            pr_file_url = f"{pr['url']}/files"
            user = {
                'node_id': pr['user']['node_id'],
                'additions': 0
            }
            contributors[user['node_id']] = user
            contributors[user['node_id']]['additions'] += fetch_pull_request_contributions(pr_file_url)
            total_additions += contributors[user['node_id']]['additions']
    else:
        print(f"{repo_pr_url} 获取失败")
        sys.exit(1)
    edges = []
    for dev in contributors:
        edges.append({
            "src": basic_info['node_id'],
            'dst': contributors[dev]['node_id'],
            "weight": (contributors[dev]['additions'] * importance_base) / total_additions
        })
    db_insert_tags(basic_info['topics'], developer_name)
    
    return {
        "node": {"id": basic_info["node_id"], "type": "project", "attributes": {"name": basic_info['name']}},
        "edges": edges
    }

def save_to_hdfs(data, path):
    """将数据直接上传到 HDFS 指定路径"""
    try:
        subprocess.run(
            ["hdfs", "dfs", "-copyFromLocal", "-f", "-", path],
            input=data.encode("utf-8"),
            check=True
        )
        print(f"Data uploaded to HDFS at: {path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error uploading data to HDFS: {e}")
        return False

def save_node_to_hdfs(nodes):
    for node in nodes:
        if save_to_hdfs(json.dumps(node, indent=4), HDFS_NODES_PATH + f"/{node['id']}.json"):
            save_to_hdfs(f"{DEVELOPER_ID}\n", HDFS_META_PATH + f"/history")
def save_edge_to_hdfs(edges):
    for edge in edges:
        if save_to_hdfs(json.dumps(edge, indent=4), HDFS_EDGES_PATH + f"/{edge['src']}_{edge['dst']}.json"):
            save_to_hdfs(f"{DEVELOPER_ID}\n", HDFS_META_PATH + f"/history")

def init():
    """初始化 DEVELOPER_ID 和 RATE_START 并打印 GitHub API 的速率限制信息"""
    global DEVELOPER_ID, RATE_START
    try:
        # 获取历史记录中的开发者ID
        output = subprocess.check_output(["hdfs", "dfs", "-cat", f"{HDFS_META_PATH}/history"], text=True)
        DEVELOPER_ID = int(output.strip())
        print(f"初始化开发者ID为: {DEVELOPER_ID}")
    except subprocess.CalledProcessError as e:
        print("无法读取 HDFS 历史记录中的开发者 ID，错误信息:", e)
        sys.exit(1)  # 直接退出程序

    # 获取 GitHub API 剩余调用速率
    rate_limit_response = requests.get("https://api.github.com/rate_limit", headers=GITHUB_HEADERS)
    if rate_limit_response.status_code == 200:
        rate_limit_data = rate_limit_response.json()
        core_limit = rate_limit_data['resources']['core']
        RATE_START = core_limit['remaining']
        print("GitHub API 核心速率限制:")
        print(f"最大请求数: {core_limit['limit']}")
        print(f"剩余请求数: {core_limit['remaining']}")
    else:
        print(f"获取 GitHub API 速率限制失败，状态码: {rate_limit_response.status_code}")
        sys.exit(1)  # 直接退出程序
def check_rate():
    # 检查速率限制
    rate_limit_response = requests.get("https://api.github.com/rate_limit", headers=GITHUB_HEADERS)
    if rate_limit_response.status_code == 200:
        rate_limit_data = rate_limit_response.json()
        core_limit = rate_limit_data['resources']['core']
        print("GitHub API 核心速率限制:")
        print(f"最大请求数: {core_limit['limit']}")
        print(f"剩余请求数: {core_limit['remaining']}")
        print(f"这一次使用了请求数量: {RATE_START - core_limit['remaining']}")
    else:
        print(f"获取 GitHub API 速率限制失败，状态码: {rate_limit_response.status_code}")
        sys.exit(1)  # 直接退出程序
    return RATE_START - core_limit['remaining'] + 100 < core_limit['remaining']
def fetch_github_data():
    """获取开发者数据并保存到 HDFS，同时检查 GitHub API 的速率限制"""
    try:
        nodes, edges = fetch_developers_data()
        # 保存数据到 HDFS
        save_node_to_hdfs(nodes)
        save_edge_to_hdfs(edges)
    except Exception as e:
        print(f"获取 GitHub 数据失败: {e}")
        sys.exit(1)  # 直接退出程序
def run_pagerunk():
    global DEVELOPER_NUM
    tmp = DEVELOPER_NUM
    process = subprocess.Popen(["bash", "pagerank.sh"])
    process.wait()
    DEVELOPER_NUM -= tmp
init()
def run_scheduler():
    while True:
        if check_rate():
            print("开始获取数据")
            fetch_github_data()
            print("结束获取数据")
            if DEVELOPER_NUM > 10:
                thread = threading.Thread(target=run_pagerunk)
                thread.start()
        else:
            time.sleep(600) # 不行就等10分钟
run_scheduler()