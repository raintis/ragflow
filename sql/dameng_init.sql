-- RAGFlow 达梦数据库初始化脚本
-- 版本: 1.0
-- 说明: 为达梦数据库创建 RAGFlow 所需的基础表结构

-- ==========================================
-- 1. 创建数据库和用户
-- ==========================================

-- 创建数据库（如果不存在）
CREATE SCHEMA IF NOT EXISTS "rag_flow";
USE "rag_flow";

-- 设置字符集
ALTER SESSION SET NLS_CHARACTERSET = 'UTF-8';

-- ==========================================
-- 2. 基础用户和权限表
-- ==========================================

-- 用户表
CREATE TABLE "user" (
    "id" VARCHAR(32) PRIMARY KEY,
    "username" VARCHAR(255) NOT NULL,
    "password" VARCHAR(255) NOT NULL,
    "email" VARCHAR(255),
    "full_name" VARCHAR(255),
    "avatar_url" VARCHAR(512),
    "status" SMALLINT DEFAULT 1,
    "is_admin" SMALLINT DEFAULT 0,
    "create_time" BIGINT NOT NULL,
    "create_date" DATE NOT NULL,
    "update_time" BIGINT NOT NULL,
    "update_date" DATE NOT NULL,
    UNIQUE ("username")
);

-- 租户表
CREATE TABLE "tenant" (
    "id" VARCHAR(32) PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "description" CLOB,
    "status" SMALLINT DEFAULT 1,
    "create_time" BIGINT NOT NULL,
    "create_date" DATE NOT NULL,
    "update_time" BIGINT NOT NULL,
    "update_date" DATE NOT NULL
);

-- 用户-租户关联表
CREATE TABLE "user_tenant" (
    "id" VARCHAR(32) PRIMARY KEY,
    "user_id" VARCHAR(32) NOT NULL,
    "tenant_id" VARCHAR(32) NOT NULL,
    "role" VARCHAR(50) DEFAULT 'normal',
    "create_time" BIGINT NOT NULL,
    "create_date" DATE NOT NULL,
    UNIQUE ("user_id", "tenant_id"),
    FOREIGN KEY ("user_id") REFERENCES "user"("id"),
    FOREIGN KEY ("tenant_id") REFERENCES "tenant"("id")
);

-- ==========================================
-- 3. 知识库相关表
-- ==========================================

-- 知识库表
CREATE TABLE "knowledge_base" (
    "id" VARCHAR(32) PRIMARY KEY,
    "tenant_id" VARCHAR(32) NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "description" CLOB,
    "status" SMALLINT DEFAULT 1,
    "create_time" BIGINT NOT NULL,
    "create_date" DATE NOT NULL,
    "update_time" BIGINT NOT NULL,
    "update_date" DATE NOT NULL,
    FOREIGN KEY ("tenant_id") REFERENCES "tenant"("id")
);

-- 文档表
CREATE TABLE "document" (
    "id" VARCHAR(32) PRIMARY KEY,
    "kb_id" VARCHAR(32) NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "type" VARCHAR(50),
    "size" BIGINT,
    "status" SMALLINT DEFAULT 1,
    "parsed_status" SMALLINT DEFAULT 0,
    "chunk_count" INTEGER DEFAULT 0,
    "create_time" BIGINT NOT NULL,
    "create_date" DATE NOT NULL,
    "update_time" BIGINT NOT NULL,
    "update_date" DATE NOT NULL,
    FOREIGN KEY ("kb_id") REFERENCES "knowledge_base"("id")
);

-- 文档分块表
CREATE TABLE "chunk" (
    "id" VARCHAR(32) PRIMARY KEY,
    "document_id" VARCHAR(32) NOT NULL,
    "content" CLOB,
    "embedding" VARCHAR(4000),
    "status" SMALLINT DEFAULT 1,
    "sequence" INTEGER,
    "create_time" BIGINT NOT NULL,
    "create_date" DATE NOT NULL,
    "update_time" BIGINT NOT NULL,
    "update_date" DATE NOT NULL,
    FOREIGN KEY ("document_id") REFERENCES "document"("id")
);

-- ==========================================
-- 4. 对话和会话表
-- ==========================================

-- 对话表
CREATE TABLE "dialog" (
    "id" VARCHAR(32) PRIMARY KEY,
    "tenant_id" VARCHAR(32) NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "description" CLOB,
    "kb_id" VARCHAR(32),
    "status" SMALLINT DEFAULT 1,
    "create_time" BIGINT NOT NULL,
    "create_date" DATE NOT NULL,
    "update_time" BIGINT NOT NULL,
    "update_date" DATE NOT NULL,
    FOREIGN KEY ("tenant_id") REFERENCES "tenant"("id"),
    FOREIGN KEY ("kb_id") REFERENCES "knowledge_base"("id")
);

-- 消息表
CREATE TABLE "message" (
    "id" VARCHAR(32) PRIMARY KEY,
    "dialog_id" VARCHAR(32) NOT NULL,
    "user_id" VARCHAR(32),
    "content" CLOB,
    "role" VARCHAR(50),
    "status" SMALLINT DEFAULT 1,
    "create_time" BIGINT NOT NULL,
    "create_date" DATE NOT NULL,
    "update_time" BIGINT NOT NULL,
    "update_date" DATE NOT NULL,
    FOREIGN KEY ("dialog_id") REFERENCES "dialog"("id"),
    FOREIGN KEY ("user_id") REFERENCES "user"("id")
);

-- ==========================================
-- 5. 配置和设置表
-- ==========================================

-- 系统配置表
CREATE TABLE "config" (
    "id" VARCHAR(32) PRIMARY KEY,
    "key" VARCHAR(255) NOT NULL,
    "value" CLOB,
    "description" VARCHAR(512),
    "create_time" BIGINT NOT NULL,
    "create_date" DATE NOT NULL,
    "update_time" BIGINT NOT NULL,
    "update_date" DATE NOT NULL,
    UNIQUE ("key")
);

-- ==========================================
-- 6. 创建索引
-- ==========================================

-- 用户表索引
CREATE INDEX "idx_user_username" ON "user"("username");
CREATE INDEX "idx_user_status" ON "user"("status");
CREATE INDEX "idx_user_create_time" ON "user"("create_time" DESC);

-- 知识库表索引
CREATE INDEX "idx_kb_tenant_id" ON "knowledge_base"("tenant_id");
CREATE INDEX "idx_kb_status" ON "knowledge_base"("status");
CREATE INDEX "idx_kb_create_time" ON "knowledge_base"("create_time" DESC);

-- 文档表索引
CREATE INDEX "idx_doc_kb_id" ON "document"("kb_id");
CREATE INDEX "idx_doc_status" ON "document"("status");
CREATE INDEX "idx_doc_parsed_status" ON "document"("parsed_status");
CREATE INDEX "idx_doc_create_time" ON "document"("create_time" DESC);

-- 分块表索引
CREATE INDEX "idx_chunk_doc_id" ON "chunk"("document_id");
CREATE INDEX "idx_chunk_status" ON "chunk"("status");

-- 对话表索引
CREATE INDEX "idx_dialog_tenant_id" ON "dialog"("tenant_id");
CREATE INDEX "idx_dialog_kb_id" ON "dialog"("kb_id");
CREATE INDEX "idx_dialog_create_time" ON "dialog"("create_time" DESC);

-- 消息表索引
CREATE INDEX "idx_msg_dialog_id" ON "message"("dialog_id");
CREATE INDEX "idx_msg_user_id" ON "message"("user_id");
CREATE INDEX "idx_msg_role" ON "message"("role");
CREATE INDEX "idx_msg_create_time" ON "message"("create_time" DESC);

-- 配置表索引
CREATE INDEX "idx_config_key" ON "config"("key");

-- ==========================================
-- 7. 初始数据（可选）
-- ==========================================

-- 插入默认租户
INSERT INTO "tenant" ("id", "name", "status", "create_time", "create_date", "update_time", "update_date")
VALUES ('default_tenant', 'Default Tenant', 1, 1718424000000, TRUNC(SYSDATE()), 1718424000000, TRUNC(SYSDATE()));

-- 插入默认配置
INSERT INTO "config" ("id", "key", "value", "description", "create_time", "create_date", "update_time", "update_date")
VALUES 
    ('cfg_001', 'app.name', 'RAGFlow', 'Application name', 1718424000000, TRUNC(SYSDATE()), 1718424000000, TRUNC(SYSDATE())),
    ('cfg_002', 'app.version', '1.0.0', 'Application version', 1718424000000, TRUNC(SYSDATE()), 1718424000000, TRUNC(SYSDATE())),
    ('cfg_003', 'db.type', 'dameng', 'Database type', 1718424000000, TRUNC(SYSDATE()), 1718424000000, TRUNC(SYSDATE()));

-- ==========================================
-- 8. 完成
-- ==========================================

COMMIT;

-- 显示初始化结果
SELECT 'RAGFlow DaMeng database initialized successfully!' AS result FROM DUAL;
