SET NAMES utf8mb4;
USE evalroute_gateway;


CREATE TABLE IF NOT EXISTS online_answer (
	`requestLogId` BIGINT NOT NULL AUTO_INCREMENT,
	`traceId` VARCHAR(64) NOT NULL,
	question TEXT NOT NULL,
	answer TEXT NOT NULL,
	PRIMARY KEY (`requestLogId`),
	UNIQUE (`traceId`)
)

;


CREATE TABLE IF NOT EXISTS answer_feedback (
	`requestLogId` BIGINT NOT NULL AUTO_INCREMENT,
	vote INTEGER NOT NULL,
	reason VARCHAR(64),
	comment TEXT,
	`updatedAt` DATETIME(6) NOT NULL,
	PRIMARY KEY (`requestLogId`)
)

;


CREATE TABLE IF NOT EXISTS satisfaction_profile (
	id BIGINT NOT NULL AUTO_INCREMENT,
	`modelId` BIGINT NOT NULL,
	`taskType` VARCHAR(64) NOT NULL,
	`sampleCount` INTEGER NOT NULL,
	`positiveCount` INTEGER NOT NULL,
	version INTEGER NOT NULL,
	`publishedAt` DATETIME(6),
	PRIMARY KEY (id),
	CONSTRAINT uk_satisfaction_model_task UNIQUE (`modelId`, `taskType`)
)

;
