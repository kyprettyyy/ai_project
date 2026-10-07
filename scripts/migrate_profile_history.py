"""Add profile version history and seed an explicitly labelled current baseline."""
from pathlib import Path
from dotenv import dotenv_values
import pymysql
root=Path(__file__).resolve().parents[1];e=dotenv_values(root/'services/gateway/.env')
c=pymysql.connect(host=e['MYSQL_HOST'],port=int(e['MYSQL_PORT']),user=e['MYSQL_USER'],password=e['MYSQL_PASSWORD'],database=e['MYSQL_DB'])
try:
 with c.cursor() as s:
  s.execute('''CREATE TABLE IF NOT EXISTS model_profile_history (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, modelKey VARCHAR(128) NOT NULL,
 taskType VARCHAR(64) NOT NULL,profileVersion INT NOT NULL,snapshot JSON NOT NULL,
 recordedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uk_profile_history_version(modelKey,taskType,profileVersion))''')
  s.execute('''INSERT IGNORE INTO model_profile_history(modelKey,taskType,profileVersion,snapshot,recordedAt)
 SELECT modelKey,taskType,profileVersion,JSON_OBJECT('quality',qualityScore*100,'latency',latencyScore*100,
 'cost',costScore*100,'reliability',reliabilityScore*100,'samples',sampleCount,'source','现有画像基线'),updateTime FROM model_capability_profile''')
  print('Profile baselines seeded:',s.rowcount)
 c.commit()
finally:c.close()
