USE evalroute_gateway;

CREATE TABLE IF NOT EXISTS model_capability_profile (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  modelId BIGINT NOT NULL,
  modelKey VARCHAR(128) NOT NULL,
  taskType VARCHAR(64) NOT NULL DEFAULT 'general',
  qualityScore DECIMAL(8,4) NOT NULL DEFAULT 0.5000,
  latencyScore DECIMAL(8,4) NOT NULL DEFAULT 0.5000,
  costScore DECIMAL(8,4) NOT NULL DEFAULT 0.5000,
  reliabilityScore DECIMAL(8,4) NOT NULL DEFAULT 0.5000,
  sampleCount INT NOT NULL DEFAULT 0,
  evaluationRunId VARCHAR(64) NULL,
  profileVersion INT NOT NULL DEFAULT 1,
  evaluatedAt DATETIME NULL,
  createTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updateTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_model_task (modelId, taskType),
  INDEX idx_task_quality (taskType, qualityScore),
  INDEX idx_evaluation_run (evaluationRunId)
) COMMENT 'Evaluation-derived model capability profile';

CREATE TABLE IF NOT EXISTS routing_decision (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  traceId VARCHAR(64) NOT NULL,
  evaluationRunId VARCHAR(64) NULL,
  taskType VARCHAR(64) NOT NULL DEFAULT 'general',
  strategy VARCHAR(32) NOT NULL,
  requestedModel VARCHAR(128) NULL,
  selectedModelId BIGINT NULL,
  selectedModelKey VARCHAR(128) NULL,
  qualityWeight DECIMAL(6,4) NOT NULL,
  latencyWeight DECIMAL(6,4) NOT NULL,
  costWeight DECIMAL(6,4) NOT NULL,
  reliabilityWeight DECIMAL(6,4) NOT NULL,
  finalScore DECIMAL(10,6) NULL,
  candidateSnapshot JSON NULL,
  fallbackOrder JSON NULL,
  createdAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_trace_id (traceId),
  INDEX idx_task_created (taskType, createdAt),
  INDEX idx_eval_run (evaluationRunId)
) COMMENT 'Auditable multi-objective routing decisions';

ALTER TABLE request_log
  ADD COLUMN evaluationRunId VARCHAR(64) NULL AFTER traceId,
  ADD COLUMN taskType VARCHAR(64) NULL AFTER requestType,
  ADD COLUMN providerName VARCHAR(64) NULL AFTER modelName,
  ADD INDEX idx_evaluationRunId (evaluationRunId),
  ADD INDEX idx_taskType (taskType);

-- Routing capability metadata used by hard constraints and task matching.
-- These updates are idempotent and also repair databases initialized by older revisions.
UPDATE model SET capabilities='["chat","summarization","classification","extraction"]'
WHERE modelKey IN ('qwen-plus', 'qwen-turbo', 'deepseek-chat');
UPDATE model SET capabilities='["chat","reasoning","math","code"]'
WHERE modelKey IN ('qwen-max', 'deepseek-reasoner', 'glm-4.7', 'glm-4.6');
UPDATE model SET capabilities='["chat","code"]'
WHERE modelKey IN ('deepseek-coder', 'glm-4.7-flash');
UPDATE model SET capabilities='["image"]'
WHERE modelKey IN ('qwen-image-plus', 'cogview-3-plus');

USE evalroute_evaluation;

CREATE TABLE IF NOT EXISTS model_profile_snapshot (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  modelName VARCHAR(128) NOT NULL,
  taskType VARCHAR(64) NOT NULL DEFAULT 'general',
  qualityScore DECIMAL(8,4) NOT NULL,
  latencyScore DECIMAL(8,4) NOT NULL,
  costScore DECIMAL(8,4) NOT NULL,
  reliabilityScore DECIMAL(8,4) NOT NULL,
  sampleCount INT NOT NULL DEFAULT 0,
  evaluationRunId VARCHAR(64) NULL,
  publishedAt DATETIME NULL,
  createTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updateTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_model_task (modelName, taskType),
  INDEX idx_run (evaluationRunId)
) COMMENT 'Evaluation-side capability profile snapshot';

CREATE TABLE IF NOT EXISTS benchmark_dataset (
  id VARCHAR(36) PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  version VARCHAR(32) NOT NULL,
  taskType VARCHAR(64) NOT NULL,
  description TEXT NULL,
  license VARCHAR(128) NULL,
  source VARCHAR(512) NULL,
  sampleCount INT NOT NULL DEFAULT 0,
  createTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_dataset_version (name, version)
) COMMENT 'Versioned benchmark dataset metadata';

CREATE TABLE IF NOT EXISTS benchmark_case (
  id VARCHAR(36) PRIMARY KEY,
  datasetId VARCHAR(36) NOT NULL,
  prompt TEXT NOT NULL,
  referenceAnswer TEXT NULL,
  rubric JSON NULL,
  metadata JSON NULL,
  createTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_dataset (datasetId)
) COMMENT 'Benchmark cases';
