// Reference rate snapshot: 2026-10-07, https://www.currency.me.uk/convert/usd/cny
export const USD_CNY_RATE = 6.7047
export const FX_NOTE = '人民币展示；美元金额按 2026-10-07 参考汇率 1 USD = 6.7047 CNY 换算，非银行结算价。'
export function toCny(value: unknown, currency = 'CNY'): number | null {
  if(value == null || value === '') return null
  const n = Number(value)
  if(!Number.isFinite(n)) return null
  return currency === 'CNY' ? n : currency === 'USD' ? n * USD_CNY_RATE : null
}
export function formatCny(value: unknown, currency = 'CNY', precision = 6): string {
  const n = toCny(value, currency)
  return n == null ? '未统计（币种或金额缺失）' : `¥${n.toFixed(precision)}`
}
export function formatCnyTotals(totals: Record<string, number>): string {
  let sum=0
  const entries=Object.entries(totals || {})
  if(!entries.length)return '未统计'
  for(const [currency,value] of entries){const n=toCny(value,currency);if(n==null)return '未统计（币种不明）';sum+=n}
  return formatCny(sum)
}
