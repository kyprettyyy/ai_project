<template>
<main class="page"><header><div><h1>路由分析</h1><p>模型能力、业务使用表现与模型选择依据</p></div><a-button :loading="loading" @click="load">刷新</a-button></header>
<a-alert v-if="error" :message="error" type="error" show-icon />
<a-space wrap class="filters"><a-select v-model:value="traffic" :options="[{value:'all',label:'全部调用'},{value:'online',label:'线上调用'},{value:'evaluation',label:'评测与打分'},{value:'legacy',label:'未分类历史 API 调用'}]" @change="load" style="width:210px" /><a-select v-model:value="days" :options="[{value:7,label:'最近7天'},{value:30,label:'最近30天'},{value:90,label:'最近90天'}]" @change="load" style="width:140px" /><a-select v-if="data?.isAdmin" v-model:value="userId" allow-clear placeholder="全部用户" :options="data.users.map(u=>({value:u.id,label:u.name}))" @change="changeUser" style="width:180px" /><a-select v-model:value="keyId" allow-clear placeholder="全部 API Key / 网页" :options="data?.keys.map(k=>({value:k.id,label:k.name}))" @change="load" style="width:220px" /><a-tag>{{data?.scope}} · 调用统计按筛选范围计算</a-tag></a-space>
<a-alert v-if="data" :message="data.statisticsNote" type="info" show-icon style="margin-bottom:16px" /><a-spin :spinning="loading"><template v-if="data"><section class="cards"><a-card><a-statistic title="请求数（按 trace 去重）" :value="data.summary.count" /><p>{{data.summary.logCount}} 条调用日志 · {{data.summary.cacheRequests}} 次缓存命中</p><p v-if="data.summary.untracedRecords">{{data.summary.untracedRecords}} 条旧日志无 trace，无法去重</p></a-card><a-card><a-statistic title="成功率 %" :value="data.summary.successRate??'暂无数据'" /><p>按每个请求最后一条日志判定</p><p>成功请求平均耗时：{{data.summary.latency??'未统计'}} ms</p></a-card><a-card><a-statistic title="已记录 Token 使用量" :value="data.summary.tokens" /><p>{{data.summary.unknownUsageRecords}} 条非缓存日志未记录有效用量</p></a-card><a-card title="目录价估算 · 已统计小计"><strong>{{money(data.summary.costs)}}</strong><p>{{data.summary.unpriced}} 次费用未统计</p><p>仅 Token 费用，不含原生搜索费用</p></a-card></section>
<a-tabs v-model:activeKey="tab">
<a-tab-pane key="profiles" tab="模型画像"><a-alert type="info" message="全局模型能力来自批量评测，独立于用户/API Key 筛选；各项评分归一化为 0–100。" /><a-space class="filters"><a-select v-model:value="task" :options="tasks.map(t=>({value:t,label:label(t)}))" style="width:160px" /><a-select v-model:value="model" :options="models.map(m=>({value:m,label:m}))" style="width:240px" /></a-space><a-card title="个人路由偏好" style="margin-bottom:20px">
<p>共享能力评分保持一致；个人偏好及已发布反馈影响自动路由。个人反馈不足 30 条时使用共享反馈，无共享反馈则使用能力评分。贝叶斯估计会平滑小样本偏差，反馈影响随样本增多逐步提高，最高占质量路由分的 20%。</p>
<a-space><span>我的偏好：</span><a-select v-model:value="preferenceMode" :options="[{value:'balanced',label:'均衡'},{value:'quality',label:'质量优先'},{value:'cost',label:'成本优先'},{value:'latency',label:'速度优先'}]" style="width:150px" /><a-button :loading="savingPreference" @click="savePreference">保存我的偏好</a-button></a-space>
<p v-if="personal">当前查看用户 {{personal.userId}} · 偏好 {{preferenceLabels[personal.mode]}}。用户偏好跨该用户的网页和 API Key 生效；单次请求指定的权重优先。</p>
<p v-if="personal && selected">{{personalStatus}}</p>
</a-card><section class="visuals"><a-card title="共享能力雷达图"><div ref="radarEl" class="chart" /><p class="muted">四个维度固定展示；未统计项不绘制数据点，也不计为 0 分。速度为同类任务内的相对评分，0 分表示当前比较组中平均耗时最长。</p><p v-if="selected" class="muted">任务能力 {{Number(selected.quality.toFixed(2))}} · 速度 {{Number(selected.latency.toFixed(2))}} · 成本效率 {{selected.cost == null ? '未统计' : Number(selected.cost.toFixed(2))}} · 可靠性 {{Number(selected.reliability.toFixed(2))}}</p><a-empty v-if="!selected" description="此任务暂无画像" /></a-card><a-card v-if="selected" title="评分来源与可信度"><h2>{{selected.model}}</h2><p>任务：{{label(selected.taskType)}} · 版本 {{selected.version}}</p><p>评分来源：{{selected.source}}</p><p v-if="selected.coverage">已评分 {{selected.coverage.ratedSamples}} 条 · 空回答 {{selected.coverage.emptySamples}} 条 · 有费用 {{selected.coverage.costSamples}} 条</p><p v-else>旧版本缺少评分覆盖明细</p><a-tag :color="selected.samples>=30?'green':'orange'">{{selected.samples}} 条样本 · {{selected.samples>=30?'达到批次门槛':'数据不足'}}</a-tag><p>更新时间：{{time(selected.updatedAt)}}</p><p>共享原始点赞率：{{selected.satisfaction==null?'数据不足':selected.satisfaction+'%'}}（{{selected.feedbackSamples}} 条反馈）</p><p class="muted">{{selected.qualityNote}} 用户反馈按批次发布。</p></a-card></section><a-table :data-source="profileRows" :columns="profileCols" :pagination="{pageSize:10}" row-key="model" :scroll="{x:950}"><template #bodyCell="{column,record}"><template v-if="column.dataIndex==='cost' && record.cost==null">未统计</template></template></a-table><a-card title="能力画像评分趋势" style="margin-top:20px"><p class="muted">记录启用后的批次画像版本（最近2000条全局版本）。首个点为现有画像基线，不补造历史评分。</p><div ref="trendEl" class="chart" /><a-empty v-if="!trend.length" description="暂无画像历史" /></a-card></a-tab-pane>
<a-tab-pane key="keys" tab="API Key 分析"><a-table :data-source="data.keyUsage" :columns="keyCols" row-key="name" :pagination="{pageSize:10}" :scroll="{x:1000}"><template #bodyCell="{column,record}"><template v-if="column.key==='costs'">{{money(record.costs)}}</template></template></a-table><a-card title="模型调用日志分布"><div ref="usageEl" class="chart" /><a-empty v-if="!data.usage.length" description="暂无调用" /></a-card></a-tab-pane>
<a-tab-pane key="users" tab="用户使用与反馈"><a-alert type="info" message="反馈按所选时间内产生的回答统计当前有效点赞/点踩，只以已反馈答案计算正向反馈率，不代表全体用户满意度。没有明确偏好数据时，不推断质量、成本或速度偏好。" /><a-table :data-source="data.usage" :columns="usageCols" :row-key="usageKey" :pagination="{pageSize:10}" :scroll="{x:1000}"><template #bodyCell="{column,record}"><template v-if="column.key==='costs'">{{money(record.costs)}}</template><template v-if="column.key==='satisfaction'">{{record.satisfaction==null?'数据不足':record.satisfaction+'%'}}</template></template></a-table></a-tab-pane>
<a-tab-pane key="decisions" tab="路由选择记录"><p class="muted">最近100条可见自动路由记录。固定模型不产生候选评分；未写入调用日志的失败决定暂不可见。</p><a-table :data-source="data.decisions" :columns="decisionCols" row-key="traceId" :pagination="{pageSize:10}" :scroll="{x:1000}"><template #bodyCell="{column,record}"><template v-if="column.key==='action'"><a-button type="link" @click="detail=record">查看依据</a-button></template><template v-if="column.key==='time'">{{time(record.createdAt)}}</template></template></a-table></a-tab-pane>
</a-tabs></template></a-spin>
<a-modal :open="!!detail" title="模型选择依据" :width="1000" :footer="null" @cancel="detail=null"><template v-if="detail"><p>请求 {{detail.traceId}} · {{label(detail.taskType)}}</p><p>最终选择：{{detail.selectedModel||'没有合适模型'}}</p><p>{{detail.selectionExplanation}}</p><a-space wrap><a-tag v-for="(v,k) in detail.weights" :key="k">{{k}}：{{Math.round(v*100)}}%</a-tag></a-space><a-table :data-source="detail.candidates" :columns="candidateCols" :pagination="false" row-key="modelKey"><template #bodyCell="{column,record}"><template v-if="column.key==='score'">{{record.weightedScore==null?'未参与排名':(record.weightedScore*100).toFixed(2)}}</template><template v-if="column.key==='reason'">{{record.explanation}}<p v-if="record.rejectionReasons?.length">未入选：{{record.rejectionReasons.join('；')}}</p></template></template></a-table></template></a-modal>
</main></template>
<script setup lang="ts">
import {ref,computed,onMounted,onBeforeUnmount,watch,nextTick} from 'vue'
import * as echarts from 'echarts'
import request from '@/request'
type Profile={model:string;taskType:string;quality:number;latency:number;cost:number|null;reliability:number;samples:number;version:number;updatedAt:string;source:string;satisfaction:number|null;feedbackSamples:number;qualityNote:string;coverage?:{ratedSamples:number;emptySamples:number;costSamples:number;latencySamples:number;costComplete:boolean}|null}
type Candidate={modelKey:string;weightedScore:number|null;sampleCount:number;explanation:string;rejectionReasons:string[]}
type Decision={traceId:string;taskType:string;selectedModel:string;createdAt:string;selectionExplanation:string;weights:Record<string,number>;candidates:Candidate[]}
type Usage={model:string;taskType:string;count:number;successRate:number;tokens:number;latency:number;positive:number;negative:number;satisfaction:number|null}
type History=Profile & {time:string}
type Dashboard={profileHistory:History[];isAdmin:boolean;scope:string;statisticsNote:string;summary:{count:number;logCount:number;cacheRequests:number;unknownUsageRecords:number;untracedRecords:number;latency:number|null;successRate:number|null;tokens:number;costs:Record<string,number>;unpriced:number};profiles:Profile[];usage:Usage[];keys:{id:string;name:string}[];keyUsage:{id:string|null;name:string;count:number;successRate:number;tokens:number;latency:number}[];users:{id:string;name:string}[];decisions:Decision[]}
const data=ref<Dashboard|null>(null),loading=ref(false),error=ref(''),days=ref(30),userId=ref<string>(),keyId=ref<string>(),traffic=ref('all'),task=ref('code'),model=ref(''),tab=ref('profiles'),detail=ref<Decision|null>(null)
const radarEl=ref<HTMLDivElement>(),trendEl=ref<HTMLDivElement>(),usageEl=ref<HTMLDivElement>(),charts=new Map<HTMLElement,echarts.ECharts>()
const usageKey=(r:Usage)=>r.model+r.taskType
const label=(t:string)=>({code:'编程',math:'数学',summarization:'总结',general:'通用',evaluation_judge:'AI打分',benchmark:'评测'} as Record<string,string>)[t]||t
const time=(s:string)=>s?new Date(s).toLocaleString('zh-CN'):'未更新'
const money=(c:Record<string,number>)=>Object.entries(c).map(([k,v])=>`${k==='CNY'?'¥':'$'} ${v.toFixed(6)}`).join(' / ')||'未统计'
const tasks=computed(()=>[...new Set(data.value?.profiles.map(p=>p.taskType)||[])]),models=computed(()=>[...new Set(data.value?.profiles.map(p=>p.model)||[])])
const profileRows=computed(()=>data.value?.profiles.filter(p=>p.taskType===task.value)||[]),selected=computed(()=>profileRows.value.find(p=>p.model===model.value))
const trend=computed(()=>(data.value?.profileHistory||[]).filter(h=>h.taskType===task.value&&h.model===model.value).slice().sort((a,b)=>a.version-b.version))
const profileCols=[{title:'模型',dataIndex:'model'},{title:'能力评分',dataIndex:'quality'},{title:'速度评分',dataIndex:'latency'},{title:'成本效率',dataIndex:'cost'},{title:'可靠性',dataIndex:'reliability'},{title:'样本数',dataIndex:'samples'},{title:'版本',dataIndex:'version'}]
const keyCols=[{title:'Key / 来源',dataIndex:'name'},{title:'调用日志数',dataIndex:'count'},{title:'日志成功率 %',dataIndex:'successRate'},{title:'Token',dataIndex:'tokens'},{title:'成功日志平均耗时 ms',dataIndex:'latency'},{title:'已统计费用',key:'costs'},{title:'点赞',dataIndex:'positive'},{title:'点踩',dataIndex:'negative'}]
const usageCols=[{title:'模型',dataIndex:'model'},{title:'任务',dataIndex:'taskType'},{title:'调用日志数',dataIndex:'count'},{title:'日志成功率 %',dataIndex:'successRate'},{title:'Token',dataIndex:'tokens'},{title:'成功日志平均耗时 ms',dataIndex:'latency'},{title:'点赞',dataIndex:'positive'},{title:'点踩',dataIndex:'negative'},{title:'正向反馈率',key:'satisfaction'},{title:'已统计费用',key:'costs'}]
const decisionCols=[{title:'时间',key:'time'},{title:'任务',dataIndex:'taskType'},{title:'选中模型',dataIndex:'selectedModel'},{title:'选择理由',dataIndex:'selectionExplanation',ellipsis:true},{title:'操作',key:'action'}]
const candidateCols=[{title:'候选模型',dataIndex:'modelKey'},{title:'综合分',key:'score'},{title:'样本数',dataIndex:'sampleCount'},{title:'依据',key:'reason'}]
const preferenceLabels: Record<string,string>={balanced:'均衡',quality:'质量优先',cost:'成本优先',latency:'速度优先'}
type Personal={userId:string;mode:string;batchSize:number;profiles:{model:string;taskType:string;samples:number;satisfaction:number;version:number;estimate:{posteriorMean:number;posteriorStdDev:number;routingWeight:number;priorConflict:boolean}}[];feedback:{model:string;taskType:string;samples:number}[]}
const personal=ref<Personal>()
const preferenceMode=ref('balanced'),savingPreference=ref(false)
const personalStatus=computed(()=>{
 const p=personal.value, s=selected.value
 if(!p || !s)return ''
 const published=p.profiles.find(x=>x.model===s.model && x.taskType===s.taskType) || p.profiles.find(x=>x.model===s.model && x.taskType==='general')
 const count=p.feedback.find(x=>x.model===s.model && x.taskType===s.taskType)?.samples || 0
 return published ? `个人原始点赞率 ${published.satisfaction}% · 贝叶斯满意度 ${(published.estimate.posteriorMean*100).toFixed(1)}% · 后验标准差 ${(published.estimate.posteriorStdDev*100).toFixed(1)} 个百分点 · ${published.samples} 条反馈 · 版本 ${published.version}；质量路由分中占 ${(published.estimate.routingWeight*100).toFixed(1)}%。${published.estimate.priorConflict ? '个人与群体反馈冲突，已回退中性先验。' : ''}` : `该任务已有 ${count} 条个人反馈，尚无可用个人批次；当前使用共享依据。`
})
async function savePreference(){savingPreference.value=true;try{const r=await request.post('/routing-analysis/personal/preference',{mode:preferenceMode.value});if(r.data.code!==0)throw new Error(r.data.message);await load()}catch(e){error.value=e instanceof Error?e.message:'保存失败'}finally{savingPreference.value=false}}
let seq=0
async function load(){const id=++seq;loading.value=true;error.value='';try{const r=await request.get('/routing-analysis',{params:{days:days.value,userId:userId.value,apiKeyId:keyId.value,traffic:traffic.value}});if(id!==seq)return;if(r.data.code!==0)throw new Error(r.data.message||'读取失败');data.value=r.data.data;const pr=await request.get('/routing-analysis/personal',{params:{userId:userId.value}});if(id!==seq)return;if(pr.data.code!==0)throw new Error(pr.data.message);personal.value=pr.data.data;const mine=await request.get('/routing-analysis/personal');if(id!==seq)return;preferenceMode.value=mine.data.data.mode;if(!models.value.includes(model.value))model.value=models.value[0]||'';if(!tasks.value.includes(task.value))task.value=tasks.value[0]||'general';await draw()}catch(e){if(id===seq)error.value=e instanceof Error?e.message:'读取失败'}finally{if(id===seq)loading.value=false}}
function changeUser(){keyId.value=undefined;load()}
function chart(el:HTMLElement|undefined,option:echarts.EChartsOption){if(!el)return;let c=charts.get(el);if(!c){c=echarts.init(el);charts.set(el,c)}c.setOption(option,true);c.resize()}
async function draw(){await nextTick();charts.forEach((c,el)=>{if(!el.isConnected){c.dispose();charts.delete(el)}});const p=selected.value;const axes=[{name:'任务能力',value:p?.quality},{name:'速度',value:p?.latency},{name:'成本效率',value:p?.cost},{name:'可靠性',value:p?.reliability}];
const incomplete=axes.some(x=>x.value==null);
chart(radarEl.value,{
  tooltip:{},
  radar:{center:['50%','50%'],radius:'65%',indicator:axes.map(x=>({name:x.name+(p && x.value==null?'（未统计）':''),max:100}))},
  series:!p?[]:incomplete?[{
    type:'custom',coordinateSystem:'none',data:[0],
    renderItem:(_params,api)=>{
      const cx=api.getWidth()/2,cy=api.getHeight()/2,r=Math.min(api.getWidth(),api.getHeight())*.325;
      const points=axes.map((x,i)=>x.value==null?null:{x:cx-Math.sin(i*Math.PI/2)*r*x.value/100,y:cy-Math.cos(i*Math.PI/2)*r*x.value/100});
      const children: any[]=[];
      points.forEach((point,i)=>{
        if(!point)return;
        const next=points[(i+1)%4];
        if(next)children.push({type:'line',shape:{x1:point.x,y1:point.y,x2:next.x,y2:next.y},style:{stroke:'#5470c6',lineWidth:2}});
        children.push({type:'circle',shape:{cx:point.x,cy:point.y,r:4},style:{fill:'#5470c6'}});
      });
      return {type:'group',children};
    }
  }]:[{type:'radar',data:[{name:p.model,value:axes.map(x=>x.value!),areaStyle:{opacity:.18}}]}]
});chart(trendEl.value,{tooltip:{trigger:'axis'},grid:{left:45,right:20,bottom:70},xAxis:{type:'category',data:trend.value.map(d=>time(d.time)),axisLabel:{rotate:20}},yAxis:{type:'value',min:0,max:100},legend:{data:['任务能力','速度','成本效率','可靠性']},series:([{name:'任务能力',field:'quality'},{name:'速度',field:'latency'},{name:'成本效率',field:'cost'},{name:'可靠性',field:'reliability'}] as const).map(s=>({type:'line',name:s.name,data:trend.value.map(d=>d[s.field])}))});const counts=new Map<string,number>();data.value?.usage.forEach(u=>counts.set(u.model,(counts.get(u.model)||0)+u.count));chart(usageEl.value,{tooltip:{trigger:'axis'},grid:{left:50,right:20,bottom:70},xAxis:{type:'category',data:[...counts.keys()],axisLabel:{rotate:20}},yAxis:{type:'value',name:'调用日志数'},series:[{type:'bar',data:[...counts.values()],itemStyle:{color:'#4385ed'}}]})}
function resize(){charts.forEach(c=>c.resize())}
watch([task,model,tab],draw);onMounted(()=>{load();window.addEventListener('resize',resize)});onBeforeUnmount(()=>{seq++;charts.forEach(c=>c.dispose());window.removeEventListener('resize',resize)})
</script>
<style scoped>
.page{max-width:1450px;margin:auto;padding:28px}header{display:flex;justify-content:space-between;align-items:center}h1{margin:0;font-size:26px}header p,.muted{color:#728096}.filters{margin:20px 0}.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-bottom:20px}.cards strong{font-size:23px}.visuals{display:grid;grid-template-columns:1.2fr 1fr;gap:20px;margin-bottom:20px}.chart{height:320px;width:100%}@media(max-width:800px){.cards{grid-template-columns:repeat(2,1fr)}.visuals{grid-template-columns:1fr}.page{padding:16px}}
</style>
