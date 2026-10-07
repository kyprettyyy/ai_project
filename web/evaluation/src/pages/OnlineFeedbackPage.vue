<template>
  <div style="padding:24px">
    <a-card title="线上用户反馈">
      <template #extra><a-button :loading="loading" @click="load">刷新</a-button></template>
      <p>满意率 = 点赞数 ÷ 已评价回答数；反馈覆盖率 = 已评价回答数 ÷ 可评价回答数。未评价的回答不计为满意。</p>
      <p>每个模型、每种任务类型首次累计 {{ data.batchSize }} 条反馈后发布满意度画像，之后每累计 {{ data.batchSize }} 条新增或修改反馈更新一次。准确性和完整度仍采用离线评测。</p>
      <a-alert v-if="error" type="error" :message="error" show-icon style="margin-bottom:16px" />
      <a-table :columns="columns" :data-source="data.rows" :loading="loading" :row-key="rowKey" :pagination="false" :scroll="{x:1100}">
        <template #bodyCell="{column, record}">
          <template v-if="column.key === 'satisfactionRate'">{{ percent(record.satisfactionRate) }}</template>
          <template v-if="column.key === 'feedbackCoverage'">{{ percent(record.feedbackCoverage) }}</template>
          <template v-if="column.key === 'publishedSatisfactionRate'">{{ percent(record.publishedSatisfactionRate) }}（{{ record.profileSampleCount }} 条，版本 {{ record.profileVersion }}）</template>
        </template>
      </a-table>
    </a-card>
    <a-card title="最近 50 条反馈" style="margin-top:24px">
      <a-empty v-if="!data.recent.length" description="还没有用户反馈" />
      <div v-for="item in data.recent" :key="item.requestId" style="border-bottom:1px solid #eee;padding:16px 0">
        <a-tag :color="item.vote === 1 ? 'green' : 'orange'">{{ item.vote === 1 ? '点赞' : '点踩' }}</a-tag>
        <strong>{{ item.model }}</strong> · {{ item.taskType }} · {{ item.updatedAt }}
        <p v-if="item.reason || item.comment">{{ reasons[item.reason] || '' }} {{ item.comment }}</p>
        <details><summary>查看问题和回答</summary><p style="white-space:pre-wrap">问题：{{ item.question }}</p><p style="white-space:pre-wrap">回答：{{ item.answer }}</p></details>
      </div>
    </a-card>
  </div>
</template>
<script setup lang="ts">
import {onMounted, ref} from 'vue'
import request from '@/request'
interface FeedbackRow { model:string; taskType:string; answerCount:number; feedbackCount:number; positiveCount:number; negativeCount:number; satisfactionRate:number|null; feedbackCoverage:number; publishedSatisfactionRate:number|null; profileSampleCount:number; profileVersion:number }
interface RecentFeedback {requestId:string;model:string;taskType:string;updatedAt:string;vote:number;reason:string;comment:string;question:string;answer:string}
const data = ref<{batchSize:number;rows:FeedbackRow[];recent:RecentFeedback[]}>({batchSize:30,rows:[],recent:[]})
const rowKey = (row:FeedbackRow) => row.model + ':' + row.taskType
const loading=ref(false), error=ref('')
const percent=(value:number|null) => value == null ? '暂无评价' : (value*100).toFixed(1)+'%'
const reasons:Record<string,string>={incorrect:'答案错误',incomplete:'内容不完整',irrelevant:'不符合要求',other:'其他'}
const columns=[{title:'模型',dataIndex:'model'}, {title:'任务类型',dataIndex:'taskType'}, {title:'回答数',dataIndex:'answerCount'}, {title:'反馈数',dataIndex:'feedbackCount'}, {title:'点赞',dataIndex:'positiveCount'}, {title:'点踩',dataIndex:'negativeCount'}, {title:'满意率',key:'satisfactionRate'}, {title:'反馈覆盖率',key:'feedbackCoverage'}, {title:'已发布满意度画像',key:'publishedSatisfactionRate'}]
async function load(){if(loading.value)return;loading.value=true;error.value='';try{const response=await request.get('/online-feedback',{timeout:15000});if(response.data.code!==0)throw new Error(response.data.message);data.value=response.data.data}catch(e){error.value=e instanceof Error?e.message:'加载失败'}finally{loading.value=false}}
onMounted(load)
</script>
