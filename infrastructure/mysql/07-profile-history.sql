SET NAMES utf8mb4;
USE evalroute_gateway;
CREATE TABLE IF NOT EXISTS model_profile_history (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 modelKey VARCHAR(128) NOT NULL, taskType VARCHAR(64) NOT NULL,
 profileVersion INT NOT NULL, snapshot JSON NOT NULL,
 recordedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uk_profile_history_version(modelKey,taskType,profileVersion)
);
