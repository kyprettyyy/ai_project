"""Idempotent currency migration; correct catalog prices without rebilling users."""
from pathlib import Path
import json
import pymysql
from dotenv import dotenv_values
root=Path(__file__).resolve().parents[1]
SOURCE='https://help.aliyun.com/zh/model-studio/model-pricing'
CATALOG={
 'qwen-turbo':('0.0003','0.0006',{'source':SOURCE,'verifiedAt':'2026-10-06','region':'cn-beijing','mode':'non-thinking'}),
 'deepseek-v4.1-flash':('0.002','0.008',{'source':SOURCE,'verifiedAt':'2026-10-06','region':'cn-beijing','offPeak':{'input':'1','output':'4'}}),
 'kimi-k3':('0.02','0.1',{'source':SOURCE,'verifiedAt':'2026-10-06','region':'cn-beijing'}),
}
def connect(service):
 e=dotenv_values(root/f'services/{service}/.env'); p='MYSQL' if service=='gateway' else 'DB'
 return pymysql.connect(host=e[p+'_HOST'],port=int(e[p+'_PORT']),user=e[p+'_USER'],password=e[p+'_PASSWORD'],database=e['MYSQL_DB' if service=='gateway' else 'DB_NAME'],charset='utf8mb4')
for service,columns in [('gateway',[('model','priceCurrency',"VARCHAR(8) NOT NULL DEFAULT 'UNKNOWN'"),('model','pricingConfig','VARCHAR(2048) NULL'),('request_log','costCurrency',"VARCHAR(8) NOT NULL DEFAULT 'UNKNOWN'"),('request_log','catalogCost','DECIMAL(12,6) NULL'),('request_log','pricingSnapshot','TEXT NULL')]),('evaluation',[('test_result','costCurrency',"VARCHAR(8) NOT NULL DEFAULT 'UNKNOWN'"),('test_result','pricingSnapshot','TEXT NULL')])]:
 c=connect(service)
 try:
  with c.cursor() as s:
   for table,column,definition in columns:
    s.execute('SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s',(table,column))
    if not s.fetchone()[0]: s.execute(f'ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}')
   if service=='gateway':
    for key,(ip,op,policy) in CATALOG.items():
     s.execute('UPDATE model m JOIN model_provider p ON p.id=m.providerId SET m.inputPrice=%s,m.outputPrice=%s,m.priceCurrency=%s,m.pricingConfig=%s WHERE m.modelKey=%s AND p.baseUrl LIKE %s',(ip,op,'CNY',json.dumps(policy),key,'%dashscope.aliyuncs.com%'))
     print('Catalog corrected:',key,'rows:',s.rowcount)
  c.commit()
 finally:c.close()
print('Currency columns ready. Historical balances/charge records unchanged.')
