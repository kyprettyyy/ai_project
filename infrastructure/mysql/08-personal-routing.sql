SET NAMES utf8mb4;
USE evalroute_gateway;
CREATE TABLE IF NOT EXISTS personal_satisfaction_profile (
 userId BIGINT NOT NULL, modelId BIGINT NOT NULL, taskType VARCHAR(64) NOT NULL,
 sampleCount INT NOT NULL DEFAULT 0, positiveCount INT NOT NULL DEFAULT 0,
 version INT NOT NULL DEFAULT 0, publishedAt DATETIME(6) NULL,
 PRIMARY KEY(userId,modelId,taskType)
);
CREATE TABLE IF NOT EXISTS user_routing_preference (
 userId BIGINT NOT NULL PRIMARY KEY, mode VARCHAR(32) NOT NULL DEFAULT 'balanced'
);
