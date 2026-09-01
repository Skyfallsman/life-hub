#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热搜 / 快讯抓取脚本
-------------------
抓取多个信源，输出统一的 news.json，供看板页面渲染。

设计原则：
1. 单源失败不影响整体（try/except 包裹，失败则该源 ok=False 并跳过）
2. 优先用官方公开接口；拿不到就优雅降级，不伪造数据
3. 只依赖 Python 标准库，GitHub Actions 上零安装即可跑

用法：
    python fetch_hot.py            # 输出到同目录 news.json
    python fetch_hot.py out.json   # 自定义输出路径
"""
import urllib.request
import urllib.error
import urllib.parse
import json
import re
import sys
import os
from datetime import datetime, timedelta, timezone

# ---------- 配置 ----------
UA_MOBILE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
UA_PC = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

TIMEOUT = 15
MAX_ITEMS = 20          # 每个源最多取多少条
CST_TZ = timezone(timedelta(hours=8))  # 北京时间时区对象（fromtimestamp 需要 tzinfo，不能用 timedelta）
CST = CST_TZ            # 兼容旧引用


def get(url, ua=UA_MOBILE, referer=None, timeout=TIMEOUT):
    """GET 请求，返回文本；失败抛异常"""
    headers = {'User-Agent': ua, 'Accept': '*/*'}
    if referer:
        headers['Referer'] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'ignore')


def clean(s):
    """去 HTML 标签、去空白、反转义"""
    if not s:
        return ''
    s = re.sub(r'<[^>]+>', '', s)
    s = (s.replace('&nbsp;', ' ').replace('&amp;', '&')
          .replace('&quot;', '"').replace('&#39;', "'").replace('&lt;', '<').replace('&gt;', '>'))
    return re.sub(r'\s+', ' ', s).strip()


# ---------- 各信源 ----------
def baidu_hot():
    """百度热搜（实时榜）——页面结构常变，用多种模式依次尝试"""
    h = get('https://top.baidu.com/board?tab=realtime', ua=UA_MOBILE)
    items, seen = [], set()

    def add(t):
        t = clean(t)
        if not t or t in seen or len(t) < 2:
            return
        seen.add(t)
        items.append({'t': t, 'u': 'https://www.baidu.com/s?wd=' + urllib.parse.quote(t)})

    # 模式 1：内嵌 JSON 的 query 字段（最常见）
    for m in re.finditer(r'"query":"(.*?)"', h):
        add(m.group(1))
        if len(items) >= MAX_ITEMS:
            return items
    # 模式 2：word 字段
    for m in re.finditer(r'"word":"(.*?)"', h):
        add(m.group(1))
        if len(items) >= MAX_ITEMS:
            return items
    # 模式 3：HTML 标题块
    for m in re.finditer(r'c-single-text-ellipsis[^>]*>(.*?)</div>', h, re.S):
        add(m.group(1))
        if len(items) >= MAX_ITEMS:
            return items
    return items


def wscn_live():
    """华尔街见闻 · 实时快讯——官方 JSON API，每条带独立原文链接"""
    api = ('https://api-one-wscn.awtmt.com/apiv1/content/lives'
           '?channel=global-channel&client=pc&limit=%d' % MAX_ITEMS)
    j = json.loads(get(api, ua=UA_PC, referer='https://wallstreetcn.com/'))
    items = []
    for it in j.get('data', {}).get('items', []):
        text = clean(it.get('text') or it.get('content') or it.get('title') or '')
        if not text:
            continue
        uri = it.get('uri') or ('https://wallstreetcn.com/livenews/%s' % it.get('id'))
        ts = it.get('display_time') or it.get('publish_time')
        tstr = ''
        if isinstance(ts, (int, float)):
            tstr = datetime.fromtimestamp(ts, CST).strftime('%H:%M')
        items.append({'t': text, 'u': uri, 'time': tstr})
        if len(items) >= MAX_ITEMS:
            break
    return items


def weibo_hot():
    """微博热搜——官方 ajax 接口，常需登录态/Cookie，失败即跳过"""
    j = json.loads(get('https://weibo.com/ajax/side/hotSearch', ua=UA_PC,
                       referer='https://weibo.com/'))
    items = []
    for band in j.get('data', {}).get('realtime', []):
        word = clean(band.get('word') or band.get('note') or '')
        if not word:
            continue
        items.append({
            't': word,
            'u': 'https://s.weibo.com/weibo?q=' + urllib.parse.quote('#%s#' % word),
            'hot': band.get('num') or band.get('realpos') or '',
        })
        if len(items) >= MAX_ITEMS:
            break
    return items


def zhihu_hot():
    """知乎热榜——官方 API，常返回 401 需登录态，失败即跳过"""
    j = json.loads(get('https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=%d'
                       % MAX_ITEMS, ua=UA_PC, referer='https://www.zhihu.com/hot'))
    items = []
    for d in j.get('data', []):
        target = d.get('target', {})
        title = clean(target.get('title') or d.get('detail_text') or '')
        if not title:
            continue
        url = 'https://www.zhihu.com/question/%s' % target.get('id') if target.get('id') else \
              'https://www.zhihu.com/hot'
        items.append({'t': title, 'u': url, 'hot': d.get('detail_text', '')})
        if len(items) >= MAX_ITEMS:
            break
    return items


def cls_telegraph():
    """财联社电报——接口路径常变动，失败即跳过"""
    api = ('https://www.cls.cn/nodeapi/telegraphList?app=CailianpressWeb&category=&'
           'hasFirstVipArticle=1&lastTime=&os=web&rn=%d&sv=7.7.5' % MAX_ITEMS)
    j = json.loads(get(api, ua=UA_PC, referer='https://www.cls.cn/telegraph'))
    items = []
    for d in j.get('data', {}).get('roll_data', []) or []:
        text = clean(d.get('title') or d.get('content') or d.get('brief') or '')
        if not text:
            continue
        items.append({
            't': text,
            'u': 'https://www.cls.cn/detail/%s' % d.get('id') if d.get('id') else 'https://www.cls.cn/telegraph',
            'time': datetime.fromtimestamp(d['time'], CST).strftime('%H:%M') if d.get('time') else '',
        })
        if len(items) >= MAX_ITEMS:
            break
    return items


# ---------- 主流程 ----------
SOURCES = [
    ('baidu',  '百度热搜',    baidu_hot),
    ('wscn',   '华尔街见闻',  wscn_live),
    ('weibo',  '微博热搜',    weibo_hot),
    ('zhihu',  '知乎热榜',    zhihu_hot),
    ('cls',    '财联社电报',  cls_telegraph),
]


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'news.json')
    now = datetime.now(CST_TZ)
    # 读取上次结果，供本次抓取失败时兜底（反爬是常态，不能让页面开天窗）
    prev = {}
    if os.path.exists(out):
        try:
            with open(out, encoding='utf-8') as f:
                prev = {s['key']: s for s in json.load(f).get('sources', [])}
        except Exception:
            prev = {}
    result = {
        'updated': now.strftime('%Y-%m-%d %H:%M'),
        'updated_ts': int(now.timestamp()),
        'sources': [],
    }
    for key, name, fn in SOURCES:
        items, ok, err, cached = [], False, '', False
        try:
            items = fn()
            ok = bool(items)
        except urllib.error.HTTPError as e:
            err = 'HTTP %s' % e.code
        except Exception as e:
            err = type(e).__name__
        # 本次失败 → 沿用上一次成功的数据，标记 cached
        if not ok and key in prev and prev[key].get('items'):
            items = prev[key]['items']
            ok, cached = True, True
            err = err + '（用上次缓存）' if err else '上次缓存'
        result['sources'].append({
            'key': key, 'name': name, 'ok': ok, 'cached': cached,
            'count': len(items), 'items': items, 'err': err,
        })
        flag = '缓存' if cached else ('OK  ' if ok else 'FAIL')
        print('%-12s %s %2d 条  %s' % (name, flag, len(items), err))

    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    ok_count = sum(1 for s in result['sources'] if s['ok'])
    print('\n更新于 %s ｜ %d/%d 个源可用 → %s' % (result['updated'], ok_count, len(SOURCES), out))


if __name__ == '__main__':
    main()
