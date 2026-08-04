# 数据库初始化

-- 设置字符集
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
USE evalroute_evaluation;

-- 创建库
create database if not exists ai_eval CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 切换库
use evalroute_evaluation;

-- 用户表
create table if not exists user
(
    id                    bigint auto_increment comment 'id' primary key,
    userAccount           varchar(256)                           not null comment '账号',
    userPassword          varchar(512)                           not null comment '密码',
    userName              varchar(256)                           null comment '用户昵称',
    userAvatar            varchar(1024)                          null comment '用户头像',
    userProfile           varchar(512)                           null comment '用户简介',
    userRole              varchar(256) default 'user'            not null comment '用户角色：user/admin',
    dailyBudget           decimal(10, 4)                         null comment '日预算限额(USD)',
    monthlyBudget         decimal(10, 4)                         null comment '月预算限额(USD)',
    budgetAlertThreshold  int          default 80                not null comment '预算预警阈值(百分比，默认80%)',
    editTime              datetime     default CURRENT_TIMESTAMP not null comment '编辑时间',
    createTime            datetime     default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime            datetime     default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete              tinyint      default 0                 not null comment '是否删除',
    UNIQUE KEY uk_userAccount (userAccount),
    INDEX idx_userName (userName)
) comment '用户' collate = utf8mb4_unicode_ci;


-- 对话记录表 (MVP核心表)
create table if not exists conversation
(
    id                  varchar(36) primary key comment '对话唯一标识',
    userId              bigint                             not null comment '用户ID',
    title               varchar(200)                       null comment '对话标题',
    conversationType    varchar(20)                        not null comment '对话类型: side_by_side/prompt_lab/battle',
    models              json                               not null comment '参与的模型列表',
    codePreviewEnabled  tinyint  default 0                 not null comment '是否启用代码预览（1-启用 0-不启用）',
    isAnonymous         tinyint  default 0                 not null comment '是否为匿名模式（1-匿名 0-非匿名）',
    modelMapping        json                               null comment '模型匿名映射关系',
    totalTokens         int      default 0                 null comment '总Token消耗',
    totalCost           decimal(10, 4) default 0           null comment '总成本(USD)',
    createTime          datetime default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime          datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete            tinyint  default 0                 not null comment '逻辑删除',
    index idx_user_created (userId, createTime desc, isDelete),
    index idx_type (conversationType, isDelete),
    index idx_code_preview (codePreviewEnabled, isDelete)
) comment '对话记录表' collate = utf8mb4_unicode_ci;

-- 对话消息表 (MVP核心表)
create table if not exists conversation_message
(
    id              varchar(36) primary key comment '消息唯一标识',
    conversationId  varchar(36)                        not null comment '对话ID',
    userId          bigint                             not null comment '用户ID',
    messageIndex    int                                not null comment '消息序号(从0开始)',
    role            varchar(20)                        not null comment '角色: user/assistant',
    modelName       varchar(100)                       null comment '模型名称(assistant消息)',
    variantIndex    int                                null comment '变体索引(用于prompt_lab，user和assistant消息)',
    content         text                               not null comment '消息内容',
    images          json                               null comment '图片URL列表',
    toolsUsed       json                               null comment '工具调用信息（JSON，含联网搜索关键词/来源等）',
    responseTimeMs  int                                null comment '响应时间(毫秒)',
    inputTokens     int                                null comment '输入Token数',
    outputTokens    int                                null comment '输出Token数',
    cost            decimal(10, 6)                     null comment '成本(USD)',
    reasoning       text                               null comment '思考过程（thinking模式）',
    codeBlocks      text                               null comment '代码块列表（JSON格式）',
    createTime      datetime default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime      datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete        tinyint  default 0                 not null comment '逻辑删除',
    index idx_conversation (conversationId, messageIndex),
    index idx_model (modelName, isDelete),
    index idx_user (userId, isDelete),
    index idx_variant (variantIndex, isDelete)
) comment '对话消息表' collate = utf8mb4_unicode_ci;

-- 模型信息表（存储从Gateway同步的模型列表）
create table if not exists model
(
    id              varchar(100) primary key comment '模型ID（Gateway格式，如：openai/gpt-4o）',
    name            varchar(200)                       not null comment '模型显示名称',
    description     text                               null comment '模型描述',
    provider        varchar(100)                       null comment '提供商（如：OpenAI, Anthropic）',
    contextLength   int                                null comment '上下文长度（tokens）',
    inputPrice      decimal(10, 6)                     null comment '输入价格（每百万tokens，美元）',
    outputPrice     decimal(10, 6)                     null comment '输出价格（每百万tokens，美元）',
    recommended     tinyint      default 0             not null comment '是否推荐（1-推荐 0-不推荐）',
    isChina         tinyint      default 0             not null comment '是否国内模型（1-国内 0-国外）',
    supportsMultimodal tinyint   default 0             not null comment '是否支持多模态(图片)',
    supportsImageGen  tinyint    default 0             not null comment '是否支持图片生成',
    supportsToolCalling tinyint  default 0             not null comment '是否支持工具/函数调用（用于开启联网搜索等）',
    tags            varchar(500)                       null comment '标签（JSON数组字符串）',
    rawData         text                               null comment 'Gateway原始数据（JSON）',
    totalTokens     bigint       default 0             not null comment '累计使用Token数',
    totalCost       decimal(12, 6) default 0           not null comment '累计花费（美元）',
    createTime      datetime     default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime      datetime     default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete        tinyint      default 0             not null comment '逻辑删除',
    index idx_provider (provider, isDelete),
    index idx_recommended (recommended, isDelete),
    index idx_updateTime (updateTime),
    index idx_list (isDelete, isChina, recommended, updateTime)
) comment '模型信息表' collate = utf8mb4_unicode_ci;



-- 用户评分表
create table if not exists rating
(
    id              varchar(36) primary key comment '评分唯一标识',
    conversationId  varchar(36)                        not null comment '对话ID',
    messageIndex    int                                not null comment '消息序号(对应某一轮对话)',
    userId          bigint                             not null comment '用户ID',
    ratingType      varchar(20)                        not null comment '评分类型: left_better/right_better/tie/both_bad/variant_N',
    winnerModel     varchar(100)                       null comment '获胜模型',
    loserModel      varchar(100)                       null comment '失败模型',
    winnerVariantIndex int                             null comment '获胜变体索引(用于prompt_lab)',
    loserVariantIndex  int                             null comment '失败变体索引(用于prompt_lab)',
    createTime      datetime default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime      datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete        tinyint  default 0                 not null comment '逻辑删除',
    unique key uk_conversation_message_user (conversationId, messageIndex, userId, isDelete),
    index idx_conversation (conversationId, isDelete),
    index idx_user (userId, isDelete),
    index idx_winner (winnerModel, isDelete)
) comment '用户评分表' collate = utf8mb4_unicode_ci;

-- 场景表 (阶段5: 场景化批量测试)
create table if not exists scene
(
    id          varchar(36) primary key comment '场景唯一标识',
    userId      bigint                             null comment '创建用户ID(预设场景为NULL)',
    name        varchar(100)                       not null comment '场景名称',
    description text                               null comment '场景描述',
    category    varchar(50)                        null comment '分类:编程/数学/文案等',
    isPreset    tinyint      default 0             not null comment '是否为预设场景(1-预设 0-自定义)',
    isActive    tinyint      default 1             not null comment '是否启用(1-启用 0-禁用)',
    createTime  datetime     default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime  datetime     default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete    tinyint      default 0             not null comment '逻辑删除',
    index idx_category (category, isDelete),
    index idx_user (userId, isDelete),
    index idx_preset (isPreset, isDelete)
) comment '测试场景表' collate = utf8mb4_unicode_ci;
-- 场景提示词表 (阶段5: 场景化批量测试)
create table if not exists scene_prompt
(
    id              varchar(36) primary key comment '提示词唯一标识',
    sceneId         varchar(36)                        not null comment '场景ID',
    userId          bigint                             not null comment '用户ID',
    promptIndex     int                                not null comment '提示词序号',
    title           varchar(200)                       not null comment '提示词标题',
    content         text                               not null comment '提示词内容',
    difficulty      varchar(20)                        null comment '难度: easy/medium/hard',
    tags            json                               null comment '标签数组',
    expectedOutput  text                               null comment '期望输出(可选)',
    createTime      datetime     default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime      datetime     default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete        tinyint      default 0             not null comment '逻辑删除',
    index idx_scene (sceneId, promptIndex),
    index idx_user (userId, isDelete)
) comment '场景提示词表' collate = utf8mb4_unicode_ci;
-- 批量测试任务表 (阶段5: 场景化批量测试)
create table if not exists test_task
(
    id                  varchar(36) primary key comment '任务唯一标识',
    userId              bigint                             not null comment '用户ID',
    name                varchar(200)                       null comment '任务名称',
    sceneId             varchar(36)                        not null comment '场景ID',
    models              json                               not null comment '测试的模型列表',
    status              varchar(20)                         not null comment '状态: pending/running/completed/failed/cancelled',
    config json DEFAULT NULL COMMENT '任务配置参数(JSON格式，包含temperature、topP等)',
    totalSubtasks       int      default 0                 not null comment '子任务总数',
    completedSubtasks   int      default 0                 not null comment '已完成子任务数',
    startedAt           datetime                           null comment '开始时间',
    completedAt         datetime                           null comment '完成时间',
    createTime          datetime default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime          datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete            tinyint  default 0                 not null comment '逻辑删除',
    index idx_user_created (userId, createTime desc, isDelete),
    index idx_status (status, isDelete),
    index idx_scene (sceneId, isDelete)
) comment '批量测试任务表' collate = utf8mb4_unicode_ci;

-- 批量测试结果表 (阶段5: 场景化批量测试)
create table if not exists test_result
(
    id              varchar(36) primary key comment '结果唯一标识',
    taskId           varchar(36)                        not null comment '任务ID',
    userId           bigint                             not null comment '用户ID',
    sceneId          varchar(36)                        not null comment '场景ID',
    promptId         varchar(36)                        not null comment '提示词ID',
    modelName        varchar(100)                       not null comment '模型名称',
    inputPrompt      text                               not null comment '输入提示词',
    outputText       text                               not null comment '输出内容',
    reasoning        text                               null comment '思考过程内容',
    responseTimeMs   int                                null comment '响应时间(毫秒)',
    inputTokens      int                                null comment '输入Token数',
    outputTokens     int                                null comment '输出Token数',
    cost             decimal(10, 6)                     null comment '成本(USD)',
    userRating       int                                null comment '用户评分(1-5)',
    aiScore          json                               null comment 'AI评分详情(多个评委模型的评分)',
    createTime       datetime default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime       datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete        tinyint  default 0                 not null comment '逻辑删除',
    index idx_task (taskId, isDelete),
    index idx_task_create (taskId, createTime),
    index idx_model (modelName, isDelete),
    index idx_user (userId, isDelete),
    index idx_scene (sceneId, isDelete),
    index idx_prompt (promptId, isDelete)
) comment '批量测试结果表' collate = utf8mb4_unicode_ci;

-- 用户-模型使用统计表
create table if not exists user_model_usage
(
    id              varchar(36) primary key comment '记录唯一标识',
    userId          bigint                             not null comment '用户ID',
    modelName       varchar(100)                       not null comment '模型名称',
    totalTokens     bigint       default 0             not null comment '累计使用Token数',
    totalCost       decimal(12, 6) default 0           not null comment '累计花费（美元）',
    createTime      datetime     default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime      datetime     default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete        tinyint      default 0             not null comment '逻辑删除',
    unique key uk_user_model (userId, modelName, isDelete),
    index idx_user (userId, isDelete),
    index idx_model (modelName, isDelete)
) comment '用户-模型使用统计表' collate = utf8mb4_unicode_ci;

-- 提示词模板表 (阶段8: 提示词模板库)
create table if not exists prompt_template
(
    id              varchar(36) primary key comment '模板唯一标识',
    userId          bigint                             null comment '用户ID(预设模板为NULL)',
    name            varchar(100)                       not null comment '模板名称',
    description     text                               null comment '模板描述',
    strategy        varchar(50)                        not null comment '策略类型: direct/cot/role_play/few_shot',
    content         text                               not null comment '模板内容(支持占位符)',
    variables       json                               null comment '变量列表(JSON数组)',
    category        varchar(50)                        null comment '分类',
    isPreset        tinyint      default 0             not null comment '是否为预设模板(1-预设 0-自定义)',
    usageCount      int          default 0             not null comment '使用次数',
    isActive        tinyint      default 1             not null comment '是否启用(1-启用 0-禁用)',
    createTime      datetime     default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime      datetime     default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete        tinyint      default 0             not null comment '逻辑删除',
    index idx_user (userId, isDelete),
    index idx_strategy (strategy, isDelete),
    index idx_preset (isPreset, isDelete),
    index idx_category (category, isDelete),
    index idx_list_pt (isDelete, isPreset, usageCount, createTime)
) comment '提示词模板表' collate = utf8mb4_unicode_ci;

-- 初始化预设模板数据
