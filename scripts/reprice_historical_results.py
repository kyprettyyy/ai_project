"""Reprice the requested report only, with restorable result and model backups."""
import sys,json
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from pathlib import Path
from dotenv import dotenv_values
import pymysql
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'services/evaluation'))
from app.utils.catalog_cost import estimate_cost
TASK='418913fb-924c-4b20-89c8-a710f1bb48e4'
e=dotenv_values(root/'services/evaluation/.env')
c=pymysql.connect(host=e['DB_HOST'],port=int(e['DB_PORT']),user=e['DB_USER'],password=e['DB_PASSWORD'],database=e['DB_NAME'],charset='utf8mb4')
prices={'qwen-turbo':(.3,.6,{}),'deepseek-v4.1-flash':(2,8,{'offPeak':{'input':1,'output':4}}),'kimi-k3':(20,100,{})}
try:
 with c.cursor() as s:
  s.execute('SELECT id,modelName,inputTokens,outputTokens,cost,costCurrency,pricingSnapshot,createTime FROM test_result WHERE taskId=%s',(TASK,));rows=s.fetchall()
  s.execute('SELECT id,rawData,inputPrice,outputPrice FROM model WHERE id IN (%s,%s,%s)',tuple(prices));models=s.fetchall()
  backup=root/'.runtime'/('cost-backup-'+datetime.now().strftime('%Y%m%d%H%M%S')+'.json');backup.write_text(json.dumps({'task':TASK,'results':rows,'models':models},default=str));backup.chmod(0o600)
  for rid,key,inp,out,old,currency,snapshot,created in rows:
   if snapshot or key not in prices:continue
   ip,op,policy=prices[key];policy['source']='https://help.aliyun.com/zh/model-studio/model-pricing'
   cost,snap=estimate_cost(inp,out,ip,op,'CNY',policy,created.replace(tzinfo=ZoneInfo('Asia/Shanghai')))
   snap.update(historicalRepriced=True,previousCost=str(old),previousCurrency=currency)
   s.execute('UPDATE test_result SET cost=%s,costCurrency=%s,pricingSnapshot=%s WHERE id=%s AND taskId=%s',(cost,'CNY',json.dumps(snap),rid,TASK))
  for mid,raw,oldip,oldop in models:
   ip,op,policy=prices[mid];obj=json.loads(raw or '{}');obj['pricing']={'prompt':str(Decimal(str(ip))/1000000),'completion':str(Decimal(str(op))/1000000),'currency':'CNY','policy':policy}
   s.execute('UPDATE model SET inputPrice=%s,outputPrice=%s,rawData=%s WHERE id=%s',(ip,op,json.dumps(obj),mid))
  s.execute('SELECT modelName,SUM(cost) FROM test_result WHERE taskId=%s GROUP BY modelName',(TASK,));print('Answer estimates CNY:',s.fetchall())
 c.commit()
finally:c.close()
