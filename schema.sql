-- 创建 developers 表，用于存储开发者的基本信息
CREATE TABLE developers (
    name VARCHAR(100) primary key,  -- 开发者的唯一标识（名字），作为主键
    score DOUBLE PRECISION,         -- 开发者的得分，用于排名
    country VARCHAR(50),            -- 开发者的国家
    country_trust INT CHECK (country_trust BETWEEN 0 AND 100)  -- 国家信任度，值在 0 到 100 之间
);

-- 创建 has_tag 表，用于存储开发者和标签的关系
CREATE TABLE has_tag (
    name VARCHAR(50),               -- 标签名称
    developer_name VARCHAR(100),    -- 开发者名称，与 developers 表的 name 字段关联
    count BIGINT,                   -- 标签的使用次数
    PRIMARY KEY (name, developer_name)  -- 标签名和开发者名的组合作为主键
);

-- 为 has_tag 表中的 developer_name 列创建索引，以提高查询效率
CREATE INDEX idx_has_tag_developer_name ON has_tag(developer_name);

-- 创建 github_tag_count 表，用于存储 GitHub 上的标签计数
CREATE TABLE github_tag_count (
    name VARCHAR(100) primary key,  -- 标签名称，作为主键
    count BIGINT                    -- 标签的全局使用次数
);

-- 初始化 github_tag_count 表，添加全局标签 '*'，初始计数为 0
INSERT INTO github_tag_count(name, count) VALUES ('*', 0);

-- 创建 user_tag_count 表，用于存储每个开发者的标签总数
CREATE TABLE user_tag_count (
    developer_name VARCHAR(100),    -- 开发者名称，作为主键
    count BIGINT,                   -- 开发者的标签总数
    PRIMARY KEY (developer_name)
);

-- 创建函数 update_github_tag_count()，用于在 has_tag 表中插入或更新记录时更新 github_tag_count 表
CREATE OR REPLACE FUNCTION update_github_tag_count()
RETURNS TRIGGER AS $$
BEGIN
    -- 插入新的标签计数或更新已存在的标签计数
    INSERT INTO github_tag_count(name, count)
    VALUES (NEW.name, 1)
    ON CONFLICT (name) 
    DO UPDATE SET count = github_tag_count.count + 1;
    
    -- 更新全局标签 '*' 的计数，增加 1
    UPDATE github_tag_count
    SET count = count + 1
    WHERE name = '*';
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器 trg_update_github_tag_count，在 has_tag 表插入或更新记录后调用 update_github_tag_count 函数
CREATE TRIGGER trg_update_github_tag_count
AFTER INSERT OR UPDATE ON has_tag
FOR EACH ROW EXECUTE FUNCTION update_github_tag_count();

-- 创建函数 update_user_tag_count()，用于在 has_tag 表中插入或更新记录时更新 user_tag_count 表
CREATE OR REPLACE FUNCTION update_user_tag_count()
RETURNS TRIGGER AS $$
BEGIN
    -- 插入新的用户标签计数或更新已存在的用户标签计数
    INSERT INTO user_tag_count(developer_name, count)
    VALUES (NEW.developer_name, 1)
    ON CONFLICT (developer_name) 
    DO UPDATE SET count = user_tag_count.count + 1;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器 trg_update_user_tag_count，在 has_tag 表插入或更新记录后调用 update_user_tag_count 函数
CREATE TRIGGER trg_update_user_tag_count
AFTER INSERT OR UPDATE ON has_tag
FOR EACH ROW EXECUTE FUNCTION update_user_tag_count();

-- 创建视图 research_view，筛选出符合特定条件的开发者和标签信息
CREATE VIEW research_view AS
SELECT 
    h.name,                         -- 标签名称
    h.developer_name                -- 开发者名称
FROM has_tag h
JOIN github_tag_count g ON g.name = h.name
JOIN user_tag_count u ON u.developer_name = h.developer_name
JOIN github_tag_count global ON global.name = '*'
WHERE ((h.count + 1.0) / (u.count + 1.0)) / ((g.count + 1.0) / (global.count + 1.0)) > 2;
-- 仅选择那些开发者的标签使用频率显著高于全局使用频率的记录

-- 创建视图 developer_rankings，基于分数对开发者进行排名
CREATE OR REPLACE VIEW developer_rankings AS
SELECT 
    ROW_NUMBER() OVER (ORDER BY score DESC) AS rank,  -- 开发者的排名，按分数降序排列
    name,                                              -- 开发者名称
    score,                                             -- 开发者分数
    country,                                           -- 开发者国家
    country_trust                                      -- 国家信任度
FROM developers;
