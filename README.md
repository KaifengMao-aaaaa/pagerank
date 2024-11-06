# 环境
* Spark
* HDFS
* PostgreSQL
* Flusk

# 项目结构
## 文件结构
```
init.sh - 初始化脚本，初始化HDFS的数据文件结构和PostgreSql的schema
init_db.sh - 初始化数据库
init_hdfs.sh - 初始化HDFS
leaderboard.html - 前端界面
pagerank.py - 算法脚本
pagerank.sh - 运行算法脚本
schema.sql - 数据库的schema
server.py - 后端API服务器
```
## 怎么使用
安装好需要的环境。

1. 添加环境变量`.env`
```
// 数据库连接环境变量
DB_HOST='' 
DB_DATABASE=''
DB_USER=''
DB_PASSWORD=''
// Github token
GITHUB_TOKEN=token "your token"
// 为了获取物理位置必须有设备信息
USER_AGENT=''
// GPT token
OPENAI_API_KEY=''
```
这些环境变量必须添加

2. HDFS的路径
`fetch.py`和`pagerank.py`需要知道HDFS的数据储存路径和获取路径。HDFS默认位置是`/data`。同时还需要知道HDFS的端口在`pagerank.py`,默认是9000.

3. 需要下载的依赖
* GraphFrame
* dotenv
* pyspark
* psycopg2
* spacy


## 使用
1. 运行init.sh 初始化HDFS和数据库
2. 运行`fetch.py`自动获取数据。
3. 可以手动更新开发者分数通过运行`pagerank.sh`脚本或者等`fetch.py`自动更新
4. 打开后端服务器`server.py`
5. 使用前端`leaderboard.html`
6. 使用前端来查看数据，`fetch.py`的进程会保持获取数据了。
# 整体结构
## 储存
* 使用HDFS来储存节点和边的计算需要的数据
* 使用PostgreSQL来储存分数和用户信息来加速查询
## 更新
* `fetch.py`获取数据先更新到PostgreSQL,然后数据清洗之后放到HDFS来准备计算
* `Pagerank.py`更新了分数更新到PostgreSQL
## 展示
* `server.py`后端服务器通过PostgreSQL获取数据，然后发送给前端
## 数据库结构
* 开发者信息储存在表格`developers`
* 标签信息储存在三个不同的表格。`has_tag`储存了用户有一个标签的次数。`github_tag_count` 储存了整个github有每一个标签的次数。`user_tag_count `储存了一个用户有一个标签的次数。
## HDFS结构
```
data/
    /metadata/history  -> 记录上次更新到哪一个开发者
    /nodes -> 全部的节点
    /edges -> 全部的边
```
# 开发者的技术能力进行评级算法
建立在PageRank算法来实现的。节点是开发者和项目。然后边有两种类型，一种是开发者到项目，另外一种是项目到开发者。算法数据主要基于最近的PR提交。

开发者到项目的边代表的是开发者对这个项目的投入程度所以分数会由开发者流向项目来加大这个项目的影响力，权重由最近PR提交记录来决定，总体而言就是最近一段时间如果对这个项目的pr多而且代码提交量多说明投入程度高所以权重会大。

项目到开发者的边权重代表的是这个开发者对这个项目的贡献程度，如果一个开发者贡献程度高，项目会对这个开发者给予跟大的边占比。边占比的公式是`importance` * `投入程度`，这个`immportance`是由`start`和 `watch`决定的。

## 算法的运行
`fetch.py`会定时更新数据同时清洗数据到hdfs里面储存。`data/nodes`储存了全部的节点， `data/edges`储存全部的边。然后`pagerank.sh`脚本会运行`pagerank.py`来利用`spark`来进行pagerank算法运行，结果在保存回PostgreSql。

# 推测位置信息
搭配nlp的spacy包来分析用户的`location`信息，可以获取到一个其中的地理位置。获取到地理位置后调用位置信息API来返回一个国家，这个是大致估计的用户国家。后面会选择10个关注的对象，统计他们的位置取他们的频率最高的国家。如果两个一样，说明可信度非常高，不一样的话可信度不高。

# 专业领域分析
统计`topics`上是标签，会方便统计全部的标签次数`x1`，一个标签出现的次数`x2`，一个用户使用标签数的总和`y1`, 一个用户使用一个标签的次数`y2`. 一个标签在全站的占比是`x2/x1`, 一个标签在一个用户使用的占比是`y2/y1`, `y2/y1` 的系数远远大于`x2/x1`,那么说明一个用户是使用这个标签的次数比例很大，可能是这个方面的专家。

# 整理用户资料
主要依靠引导GPT来获取用户信息然后转化成HTML来插入到网站中。
# 前端
![图片描述](./img/display.png)
## Demo
基础功能
<video src="./img/基础功能.mp4" controls></video>
用户页面整理功能
<video src="./img/整理页面.mp4" controls></video>

#后端
数据展示
<video src="./img/数据.mp4" controls></video>

更多数据可以通过运行`fetch.py`获取