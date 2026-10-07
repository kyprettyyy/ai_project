from pathlib import Path
from dotenv import dotenv_values
import pymysql
root=Path(__file__).resolve().parents[1];e=dotenv_values(root/'services/gateway/.env')
c=pymysql.connect(host=e['MYSQL_HOST'],port=int(e['MYSQL_PORT']),user=e['MYSQL_USER'],password=e['MYSQL_PASSWORD'],database=e['MYSQL_DB'])
try:
 with c.cursor() as s:
  s.execute('''CREATE TABLE IF NOT EXISTS personal_satisfaction_profile (userId BIGINT NOT NULL, modelId BIGINT NOT NULL, taskType VARCHAR(64) NOT NULL, sampleCount INT NOT NULL DEFAULT 0, positiveCount INT NOT NULL DEFAULT 0, version INT NOT NULL DEFAULT 0, publishedAt DATETIME(6) NULL, PRIMARY KEY(userId,modelId,taskType))''')
  s.execute('''CREATE TABLE IF NOT EXISTS user_routing_preference (userId BIGINT NOT NULL PRIMARY KEY, mode VARCHAR(32) NOT NULL DEFAULT 'balanced')''')
 c.commit();print('Personal routing tables ready; balances and shared profiles unchanged')
finally:c.close()
