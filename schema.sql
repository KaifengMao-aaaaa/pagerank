CREATE TABLE developers (
    name VARCHAR(100) primary key,
    score DOUBLE PRECISION,
    country VARCHAR(50),
    country_trust INT CHECK (country_trust BETWEEN 0 AND 100)
);
CREATE TABLE has_tag (
    name VARCHAR(50),
    developer_name VARCHAR(100),
    count BIGINT,
    PRIMARY KEY (name, developer_name)
);
CREATE INDEX idx_has_tag_developer_name ON has_tag(developer_name);
CREATE TABLE github_tag_count (
    name VARCHAR(100) primary key,
    count BIGINT
);
INSERT INTO github_tag_count(name, count) values ('*', 0);
CREATE TABLE user_tag_count (
    developer_name VARCHAR(100),
    count BIGINT,
    PRIMARY KEY (developer_name)
);

CREATE OR REPLACE FUNCTION update_github_tag_count()
RETURNS TRIGGER AS $$
BEGIN
    -- 更新github_tag_count中的标签计数
    INSERT INTO github_tag_count(name, count)
    VALUES (NEW.name, 1)
    ON CONFLICT (name) 
    DO UPDATE SET count = github_tag_count.count + 1;
    
    -- 更新全局标签 '*' 的计数
    UPDATE github_tag_count
    SET count = count + 1
    WHERE name = '*';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_github_tag_count
AFTER INSERT OR UPDATE ON has_tag
FOR EACH ROW EXECUTE FUNCTION update_github_tag_count();



CREATE OR REPLACE FUNCTION update_user_tag_count()
RETURNS TRIGGER AS $$
BEGIN
    -- 增加 user_tag_count 中相应用户的计数
    INSERT INTO user_tag_count(developer_name, count)
    VALUES (NEW.developer_name, 1)
    ON CONFLICT (developer_name) 
    DO UPDATE SET count = user_tag_count.count + 1;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_user_tag_count
AFTER INSERT OR UPDATE ON has_tag
FOR EACH ROW EXECUTE FUNCTION update_user_tag_count();

CREATE VIEW research_view AS
SELECT 
    h.name, 
    h.developer_name
FROM has_tag h
JOIN github_tag_count g ON g.name = h.name
JOIN user_tag_count u ON u.developer_name = h.developer_name
JOIN github_tag_count global ON global.name = '*'
WHERE ((h.count + 1.0) / (u.count + 1.0)) / ((g.count + 1.0) / (global.count + 1.0)) > 2;

CREATE VIEW developer_rankings AS
SELECT 
    ROW_NUMBER() OVER (ORDER BY score DESC) AS rank, 
    name, 
    score, 
    country 
FROM developers;