"""Provider-native Chat Completions search capabilities (no external search key)."""
from urllib.parse import urlparse
CHAT_MODELS={'qwen-turbo','qwen-plus','qwen-plus-latest','qwen-max','qwen-flash','qwq-plus','deepseek-v3','deepseek-r1','deepseek-r1-0528','deepseek-v3.1','deepseek-v3.2','deepseek-v3.2-exp','deepseek-v4-flash','deepseek-v4-pro','Moonshot-Kimi-K2-Instruct','MiniMax-M2.1'}
def supports_native_search(model,provider):
 host=urlparse(provider.base_url or '').hostname or ''
 return (host.endswith('.aliyuncs.com') and ('dashscope' in host or '.maas.' in host)
         and (model.model_key in CHAT_MODELS or model.model_key.startswith(('qwen-plus-','qwen-max-','qwen-flash-','qwen3-max','qwen3.5-','qwen3.6-','qwen3.7-','qwen3.8-','deepseek-v4-flash-','deepseek-v4-pro-'))))
def search_extra(model,provider,request):
 if not request.enable_search:return {}
 if not supports_native_search(model,provider):
  raise ValueError(f'当前模型 {model.model_key} 的接口尚不支持原生联网搜索；请选择支持联网搜索的千问模型。Kimi K3 需要 Responses 搜索接口。')
 return {'enable_search':True,'search_options':{'forced_search':True,'enable_source':True,'enable_citation':True}}
