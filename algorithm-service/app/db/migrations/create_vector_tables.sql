--
-- 向量检索相关表结构
-- 用于存储术语、SQL示例和Schema信息
--

-- 术语表
CREATE TABLE IF NOT EXISTS terminologies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term VARCHAR(255) NOT NULL COMMENT '术语名称',
    definition TEXT NOT NULL COMMENT '术语定义/解释',
    category VARCHAR(100) COMMENT '分类',
    synonyms TEXT COMMENT '同义词列表，JSON格式',
    datasource_id INTEGER COMMENT '关联的数据源ID',
    oid INTEGER DEFAULT 1 COMMENT '组织ID',
    vector_version INTEGER DEFAULT 0 COMMENT '向量版本号，用于同步追踪',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (datasource_id) REFERENCES datasources(id) ON DELETE SET NULL
);

-- 术语表索引
CREATE INDEX IF NOT EXISTS idx_terminologies_datasource ON terminologies(datasource_id);
CREATE INDEX IF NOT EXISTS idx_terminologies_category ON terminologies(category);
CREATE INDEX IF NOT EXISTS idx_terminologies_oid ON terminologies(oid);

-- SQL示例表（训练示例）
CREATE TABLE IF NOT EXISTS training_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL COMMENT '自然语言问题',
    sql TEXT NOT NULL COMMENT 'SQL语句',
    explanation TEXT COMMENT '解释说明',
    datasource_type VARCHAR(50) COMMENT '数据源类型',
    datasource_id INTEGER COMMENT '关联的数据源ID',
    oid INTEGER DEFAULT 1 COMMENT '组织ID',
    vector_version INTEGER DEFAULT 0 COMMENT '向量版本号，用于同步追踪',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (datasource_id) REFERENCES datasources(id) ON DELETE SET NULL
);

-- SQL示例表索引
CREATE INDEX IF NOT EXISTS idx_training_examples_datasource ON training_examples(datasource_id);
CREATE INDEX IF NOT EXISTS idx_training_examples_type ON training_examples(datasource_type);
CREATE INDEX IF NOT EXISTS idx_training_examples_oid ON training_examples(oid);

-- Schema表（存储数据源的Schema信息）
CREATE TABLE IF NOT EXISTS schemas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datasource_id INTEGER NOT NULL UNIQUE COMMENT '数据源ID',
    schema_json TEXT NOT NULL COMMENT 'Schema信息，JSON格式',
    vector_version INTEGER DEFAULT 0 COMMENT '向量版本号，用于同步追踪',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (datasource_id) REFERENCES datasources(id) ON DELETE CASCADE
);

-- Schema表索引
CREATE INDEX IF NOT EXISTS idx_schemas_datasource ON schemas(datasource_id);

-- 触发器：自动更新updated_at字段
CREATE TRIGGER IF NOT EXISTS update_terminologies_timestamp 
AFTER UPDATE ON terminologies
BEGIN
    UPDATE terminologies SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_training_examples_timestamp 
AFTER UPDATE ON training_examples
BEGIN
    UPDATE training_examples SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_schemas_timestamp 
AFTER UPDATE ON schemas
BEGIN
    UPDATE schemas SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
