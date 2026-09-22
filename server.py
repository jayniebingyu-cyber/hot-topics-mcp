#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hot-topics-mcp — MCP server giving AI agents real-time trending-topic intelligence
Sources: Weibo / Baidu / Zhihu / Google Trends + HackerNews & StackExchange community intel.
Zero dependencies (stdlib only). Protocol: MCP over stdio (JSON-RPC 2.0).
"""
import json, urllib.request, re, sys, datetime, os, time, gzip, base64, html as html_mod, urllib.parse

UA = {'User-Agent': 'hot-topics-mcp/1.0 (trend research)'}
CACHE = {}
CACHE_TTL = 600  # 10分钟缓存

def fetch(url, timeout=20, referer=None):
    headers = dict(UA)
    if referer:
        headers['Referer'] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if raw[:2] == b'\x1f\x8b':
            raw = gzip.decompress(raw)
        return raw.decode('utf-8', 'ignore')

def cached(key, fn):
    now = time.time()
    if key in CACHE and now - CACHE[key][0] < CACHE_TTL:
        return CACHE[key][1]
    val = fn()
    CACHE[key] = (now, val)
    return val

# ---------- 数据源 ----------
def weibo():
    data = json.loads(fetch('https://weibo.com/ajax/side/hotSearch', referer='https://weibo.com/'))
    return [x['word'] for x in data['data']['realtime'][:50] if x.get('word')]

def baidu():
    data = json.loads(fetch('https://top.baidu.com/api/board?tab=realtime', referer='https://top.baidu.com/'))
    words = []
    for c in data['data']['cards']:
        for x in c.get('content', []):
            if x.get('word'):
                words.append(x['word'])
    return words[:50]

def zhihu():
    html = fetch('https://www.zhihu.com/billboard', referer='https://www.zhihu.com/')
    seen, out = set(), []
    for t in re.findall(r'"title":"([^"]{4,60})"', html):
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:50]

def google_trends():
    xml = fetch('https://trends.google.com/trending/rss?geo=US')
    return re.findall(r'<title>([^<]{4,80})</title>', xml)[1:50]

def hn_stories(query='chatgpt OR ai OR productivity'):
    url = ('https://hn.algolia.com/api/v1/search?query=' + urllib.parse.quote(query) +
           '&tags=story&hitsPerPage=15&numericFilters=points>20,created_at_i>' + str(int(time.time()) - 30*86400))
    data = json.loads(fetch(url))
    return [{'title': h.get('title'), 'points': h.get('points'), 'comments': h.get('num_comments'),
             'url': 'https://news.ycombinator.com/item?id=' + str(h.get('objectID'))} for h in data.get('hits', [])]

def se_questions(site='parenting'):
    url = ('https://api.stackexchange.com/2.3/questions?site=' + site +
           '&fromdate=' + str(int(time.time()) - 7*86400) + '&sort=votes&order=desc&pagesize=15')
    data = json.loads(fetch(url))
    items = data.get('items', [])
    if len(items) < 5:
        url2 = ('https://api.stackexchange.com/2.3/questions?site=' + site +
                '&sort=votes&order=desc&pagesize=10')
        items.extend(json.loads(fetch(url2)).get('items', []))
    return [{'title': html_mod.unescape(q.get('title', '')), 'score': q.get('score'),
             'answers': q.get('answer_count'), 'url': q.get('link')} for q in items[:15]]

SOURCES = {'weibo': weibo, 'baidu': baidu, 'zhihu': zhihu, 'google_trends': google_trends}

TRACK_KW = {
    '亲子教育': ['孩子', '儿童', '育儿', '家长', '教育', '作业', '学习', '亲子', '妈妈', '学校', '开学', '成绩', '考试', '小学生', '幼儿园', '家庭'],
    'AI工具': ['AI', 'ChatGPT', 'chatgpt', '人工智能', '大模型', 'DeepSeek', 'deepseek', 'OpenAI', 'Gemini', 'Claude', '提效', '效率', '副业', '职场', '裁员', '简历', '自动化'],
    'EN_kids': ['kids', 'children', 'parenting', 'homeschool', 'focus', 'attention', 'school', 'mom', 'routine', 'printable'],
    'EN_ai': ['chatgpt', 'ai ', 'prompt', 'productivity', 'automation', 'work', 'resume', 'job', 'openai', 'gemini', 'claude'],
}

SENSITIVE = ['死', '亡', '尸', '自杀', '坠楼', '枪', '暴', '恐怖', '爆炸', '火灾', '地震', '车祸', '失联', '失踪',
             '杀人', '谋杀', '强奸', '性侵', '猥亵', '吸毒', '诈骗案', '遇害', '遇难', '法院', '判刑', '逮捕',
             '政治', '选举', '罢工', '抗议', '游行', '冲突', '战争', '导弹', '制裁', '间谍', '泄密',
             '失明', '瘫痪', 'ICU', '绝症', '癌', '白血病', '抑郁', '跳楼', '猝死', '心梗']

def is_sensitive(t):
    return any(w in t for w in SENSITIVE)

def score_topics(titles, kws, limit=10):
    hits = []
    for t in titles:
        if is_sensitive(t):
            continue
        tl = t.lower()
        s = sum(1 for k in kws if k.lower() in tl)
        if s > 0:
            hits.append((s, t))
    hits.sort(key=lambda x: -x[0])
    return [t for s, t in hits[:limit]]

# ---------- MCP 工具实现 ----------
def tool_get_trending(args):
    track = args.get('track', 'all')
    srcs = args.get('sources') or list(SOURCES.keys())
    pools, ok = {}, []
    for name in srcs:
        if name not in SOURCES:
            continue
        try:
            pools[name] = cached(name, SOURCES[name])
            ok.append(name)
        except Exception as e:
            pools[name] = []
    cn_pool = pools.get('weibo', []) + pools.get('baidu', []) + pools.get('zhihu', [])
    en_pool = pools.get('google_trends', [])
    result = {'date': datetime.date.today().isoformat(), 'sources_ok': ok}
    if track in ('all', 'raw'):
        result['raw'] = {k: v[:20] for k, v in pools.items()}
    if track in ('all', '亲子教育'):
        result['亲子教育'] = score_topics(cn_pool, TRACK_KW['亲子教育'])
    if track in ('all', 'AI工具'):
        result['AI工具'] = score_topics(cn_pool, TRACK_KW['AI工具'])
    if track in ('all', 'EN_kids'):
        result['EN_kids'] = score_topics(en_pool, TRACK_KW['EN_kids'])
    if track in ('all', 'EN_ai'):
        result['EN_ai'] = score_topics(en_pool, TRACK_KW['EN_ai'])
    return result

REDDIT_INTEL = {
    'kids': [('se', 'parenting'), ('hn', 'parenting kids focus attention')],
    'ai': [('hn', 'chatgpt prompts productivity'), ('se', 'workplace')],
    'poa': [('se', 'expatriates'), ('hn', 'digital nomad banking address')],
}

def tool_reddit_intel(args):
    track = args.get('track', 'ai')
    out = {'track': track, 'threads': []}
    for kind, arg in REDDIT_INTEL.get(track, REDDIT_INTEL['ai']):
        try:
            if kind == 'se':
                for t in cached('se:' + arg, lambda a=arg: se_questions(a)):
                    t2 = dict(t); t2['source'] = arg + '.SE'
                    out['threads'].append(t2)
            else:
                for t in cached('hn:' + arg, lambda a=arg: hn_stories(a)):
                    t2 = dict(t); t2['source'] = 'HackerNews'
                    out['threads'].append(t2)
        except Exception:
            pass
    out['threads'] = out['threads'][:20]
    return out

TOOLS = [
    {'name': 'get_trending',
     'description': 'Real-time trending topics from Weibo/Baidu/Zhihu (China) and Google Trends (US), scored against content tracks with sensitive-topic filtering. Tracks: 亲子教育, AI工具, EN_kids, EN_ai, all, raw.',
     'inputSchema': {'type': 'object', 'properties': {
         'track': {'type': 'string', 'enum': ['亲子教育', 'AI工具', 'EN_kids', 'EN_ai', 'all', 'raw'], 'default': 'all'},
         'sources': {'type': 'array', 'items': {'type': 'string', 'enum': ['weibo', 'baidu', 'zhihu', 'google_trends']}}}}},
    {'name': 'get_reddit_intel',
     'description': 'High-engagement community threads (HackerNews + StackExchange) for Reddit GEO content research. Tracks: kids, ai, poa.',
     'inputSchema': {'type': 'object', 'properties': {
         'track': {'type': 'string', 'enum': ['kids', 'ai', 'poa'], 'default': 'ai'}}}},
]

# ---------- MCP stdio 主循环 ----------
PROTOCOL_VERSION = '2024-11-05'

def reply(rid, result=None, error=None):
    msg = {'jsonrpc': '2.0', 'id': rid}
    if error:
        msg['error'] = error
    else:
        msg['result'] = result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + '\n')
    sys.stdout.flush()

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        method = req.get('method', '')
        rid = req.get('id')
        if method == 'initialize':
            reply(rid, {'protocolVersion': PROTOCOL_VERSION,
                        'capabilities': {'tools': {}},
                        'serverInfo': {'name': 'hot-topics-mcp', 'version': '1.0.0'}})
        elif method == 'notifications/initialized':
            pass
        elif method == 'tools/list':
            reply(rid, {'tools': TOOLS})
        elif method == 'tools/call':
            name = req.get('params', {}).get('name', '')
            args = req.get('params', {}).get('arguments', {}) or {}
            try:
                if name == 'get_trending':
                    data = tool_get_trending(args)
                elif name == 'get_reddit_intel':
                    data = tool_reddit_intel(args)
                else:
                    reply(rid, error={'code': -32601, 'message': 'unknown tool: ' + name})
                    continue
                reply(rid, {'content': [{'type': 'text', 'text': json.dumps(data, ensure_ascii=False, indent=1)}]})
            except Exception as e:
                reply(rid, error={'code': -32000, 'message': repr(e)})
        elif rid is not None:
            reply(rid, error={'code': -32601, 'message': 'method not found: ' + method})

if __name__ == '__main__':
    main()
