
from pyspark.sql import SparkSession
from subprocess import check_output
import os
import requests
import subprocess
from collections import Counter
import json
from datetime import datetime
# import schedule
import time
import psycopg2
import tempfile
import spacy

# 加载预训练的模型
nlp = spacy.load("en_core_web_sm")

db_config = {
    'host': 'localhost',          # 数据库主机地址
    'database': 'github',          # 数据库名称
    'user': 'host',           # 用户名
}

conn = psycopg2.connect(**db_config)
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"
}
# HDFS 路径配置
HDFS_NODES_PATH = "hdfs:///data/nodes"
HDFS_EDGES_PATH = "hdfs:///data/edges"
HDFS_META_PATH = "hdfs:///data/metadata"
DEVELOPER_ID = 1
DEVELOPER_PAGING_LIMIT=3
PR_LIMIT = 3
RATE_START = 5000
def fetch_developers_data():
    global DEVELOPER_ID
    developer_url = f"{GITHUB_API_BASE_URL}/users?since={DEVELOPER_ID}&per_page={DEVELOPER_PAGING_LIMIT}"
    response = requests.get(developer_url, headers=GITHUB_HEADERS)
    nodes = []
    edges = []
    if response.status_code == 200:
        developers_data = response.json()
        for developer in developers_data:
            developer_info = fetch_developer_data(developer['login'], developer['node_id'])
            edges.extend(developer_info['edges'])
            nodes.extend(developer_info['node'])
    DEVELOPER_ID += DEVELOPER_PAGING_LIMIT
    return [nodes, edges]

def guess_position(text):
    doc = nlp(text)
    # 提取地理位置
    for ent in doc.ents:
        if ent.label_ == "GPE": 
            return ent
def get_country_from_location(text):
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
    followers_locations = []
    
    url = f'https://api.github.com/users/{username}/following?per_page=10'
    response = requests.get(url)
    print(response.status_code)
    followers = response.json()
    print(followers)
    for follower in followers:
        follower_location = get_user_location(follower['login'])
        followers_locations.append(follower_location)
    location_counter = Counter(followers_locations)
    most_common_location = location_counter.most_common(1)
    if most_common_location:
        location, count = most_common_location[0]
        frequency = (count / len(followers_locations)) * 100  # 计算出现频率
    else:
        location, frequency = "None", 0

    return location, frequency

def get_user_location(username):
    url = f'https://api.github.com/users/{username}'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return get_country_from_location(data.get('location'))
    return None
def infer_developer_country(developer_name):
    developer_country = get_user_location(developer_name)
    most_possible_country = get_followers_locations(developer_name)
    if developer_country != None and most_possible_country[0] == developer_country:
        return [developer_country, min(100, most_possible_country[1] + 50)]
    elif developer_country != most_possible_country[0]:
        return [developer_country, 60]
    elif developer_country == None and most_possible_country[0] != None:
        return [most_possible_country[0], min(100, most_possible_country[1])]
    else:
        return [developer_country, 0]

def fetch_repo_info(repository_url):
    repo_response = requests.get(repository_url, headers=GITHUB_HEADERS)
    if repo_response.status_code == 200:
        repo_info = repo_response.json()
        return {'name': repo_info["name"], "id" : repo_info["id"], 'node_id' : repo_info['node_id'], "star": repo_info['stargazers_count'], "watch": repo_info["subscribers_count"], "topics": repo_info["topics"]}
    return {}
def fetch_contribution_info(pr_files_url):
    pr_files_response = requests.get(pr_files_url, headers=GITHUB_HEADERS)
    total_additions = 0
    if pr_files_response.status_code == 200:
        pr_files = pr_files_response.json()
        additions = sum(file["additions"] for file in pr_files)
        total_additions += additions
    return total_additions

def fetch_developer_data(developer_name, developer_node_id):
    # 获取所有项目的urls
    search_url = f"{GITHUB_API_BASE_URL}/search/issues?q=type:pr+author:{developer_name}&per_page=100"
    response = requests.get(search_url, headers=GITHUB_HEADERS)
    repos = {}
    edges = []
    nodes = []
    nodes.append({"id": developer_node_id, 'type': 'developer', 'attributes': {'name': developer_name}})
    total_contribution = 1
    if response.status_code == 200:
        pr_data = response.json()
        pr_data = [pr for pr in pr_data['items'] if pr['pull_request']['merged_at'] != None]
        for pr in pr_data[:PR_LIMIT]:
            repository_url = pr["repository_url"]
            pr_url = f"{repository_url}/pulls/{pr['number']}/files"
            repo_node = fetch_repo_detail_info(repository_url, developer_name)
            nodes.append(repo_node['node'])
            filtered_edges = list(filter(lambda edge: edge['dst'] == developer_node_id, repo_node['edges']))
            edges.extend(filtered_edges)
            contribution = fetch_contribution_info(pr_url)
            with open('log', 'a') as f:
                print(f"{developer_node_id} contribution: {contribution} to {repo_node['node']['id']}", file=f)
                print(filtered_edges, file=f)
            total_contribution += contribution
            repos[repo_node['node']['id']] = {"node_id": repo_node['node']['id'], "contribution": contribution}
    for repo in repos:
        edges.append({"src": developer_node_id, "dst": repos[repo]['node_id'], "weight": repos[repo]["contribution"] / total_contribution})
    country = infer_developer_country(developer_name)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO developers (name, score, country,country_trust) VALUES (%s, %s, %s, %s) ON CONFLICT (name) DO NOTHING", (developer_name, 0, 'N/A' if country[0] == None else country[0], country[1]))
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
def fetch_repo_detail_info(repo_url, developer_name):
    # # https://api.github.com/repos/tehtbl/awesome-note-taking/pulls
    # repo_url = "https://api.github.com/repos/tehtbl/awesome-note-taking"
    basic_info = fetch_repo_info(repo_url)
    repo_pr_url = f"{repo_url}/pulls?state=all"
    response = requests.get(repo_pr_url, headers=GITHUB_HEADERS)
    contributors = {}
    total_additions = 1
    importance_base = basic_info['star'] * 100 + basic_info['watch'] + 1
    with open('log', 'a') as f:
        print(f"{repo_url} stars: {basic_info['star']}, watch: {basic_info['watch']}, importance_base = {importance_base}", file=f)
    if response.status_code == 200:
        pr_data = response.json()
        for pr in pr_data:
            pr_file_url = f"{pr['url']}/files"
            user = {
                'node_id': pr['user']['node_id'],
                'additions': 0
            }
            contributors[user['node_id']] = user
            contributors[user['node_id']]['additions'] += fetch_contribution_info(pr_file_url)
            total_additions += contributors[user['node_id']]['additions']
    edges = []
    for dev in contributors:
        edges.append({"src": basic_info['node_id'], 'dst': contributors[dev]['node_id'], "weight": (contributors[dev]['additions'] * importance_base) / total_additions})
    db_insert_tags(basic_info['topics'], developer_name)
    return {"node": {"id": basic_info["node_id"], "type": "project", "attributes": {"name" : basic_info['name']}}, "edges": edges}

def save_to_hdfs(file, path):
    with tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json") as temp_file:
        local_path = temp_file.name
        temp_file.write(file)
        print(f"Data temporarily saved at: {local_path}")

    # 将临时文件上传到 HDFS
    sucessful = True
    try:
        subprocess.run(["hdfs", "dfs", "-put", "-f", local_path, path], check=True)
        print(f"Data uploaded to HDFS at: {path}")
    except subprocess.CalledProcessError as e:
        print(f"Error uploading file to HDFS: {e}")
        sucessful = False
    finally:
        # 删除本地临时文件
        os.remove(local_path)
        print(f"Temporary file {local_path} deleted.")
    return sucessful

def save_node_to_hdfs(nodes):
    for node in nodes:
        if save_to_hdfs(json.dumps(node, indent=4), HDFS_NODES_PATH + f"/{node['id']}.json"):
            save_to_hdfs(f"{DEVELOPER_ID}\n", HDFS_META_PATH + f"/history")
def save_edge_to_hdfs(edges):
    for edge in edges:
        if save_to_hdfs(json.dumps(edge, indent=4), HDFS_EDGES_PATH + f"/{edge['src']}_{edge['dst']}.json"):
            save_to_hdfs(f"{DEVELOPER_ID}\n", HDFS_META_PATH + f"/history")

def init():
    global DEVELOPER_ID
    global RATE_START
    output = subprocess.check_output(["hdfs", "dfs", "-cat", f"{HDFS_META_PATH}/history"], text=True)
    DEVELOPER_ID = int(output)
    rate_limit_response = requests.get("https://api.github.com/rate_limit", headers=GITHUB_HEADERS)
    rate_limit_data = rate_limit_response.json()
    core_limit = rate_limit_data['resources']['core']
    RATE_START = core_limit['remaining']
    print("Core Rate Limit:")
    print(f"Limit: {core_limit['limit']}")
    print(f"Remaining: {core_limit['remaining']}")
def fetch_github_data():
    nodes, edges = fetch_developers_data()
    save_node_to_hdfs(nodes)
    save_edge_to_hdfs(edges)
    rate_limit_response = requests.get("https://api.github.com/rate_limit", headers=GITHUB_HEADERS)
    rate_limit_data = rate_limit_response.json()
    core_limit = rate_limit_data['resources']['core']
    print("Core Rate Limit:")
    print(f"Limit: {core_limit['limit']}")
    print(f"Remaining: {core_limit['remaining']}")
init()
fetch_github_data()
# import time
# from datetime import datetime, timedelta

# def run_scheduler():
#     next_run = datetime.now() + timedelta(minutes=30)

#     while True:
#         now = datetime.now()
#         if now >= next_run:
#             fetch_github_data()
#             next_run = now + timedelta(minutes=30) 

#         time.sleep(1)
# run_scheduler()