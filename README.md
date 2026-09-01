# 热搜看板 · 一键开启自动更新

抓取脚本 + 定时任务都已写好，你只需在 GitHub 上操作 **3 步（约 3 分钟）**，之后手机打开就是最新热搜，**不用再开电脑**。

---

## 第 1 步：建仓库

1. 打开 https://github.com/new
2. 仓库名填 `gary-hot`（随便起，**建议 Private 私有**）
3. 其他保持默认，点 Create repository

## 第 2 步：上传文件

把 `mobile/` 目录里的**所有文件**上传到仓库根目录：

```
index.html          ← 日程 + 热搜看板（主页面）
news.json           ← 热搜数据（会被自动更新）
fetch_hot.py        ← 抓取脚本
manifest.json       ← PWA 配置
sw.js               ← 离线 / 自动更新
icon-192.png
icon-512.png
```

再把 `hotboard/.github/` 整个目录上传到仓库根目录（注意 `.github` 是隐藏目录，要连目录一起传）：

```
.github/workflows/hot.yml    ← 定时任务（每 30 分钟）
```

> 最简单的方法：GitHub 网页上点 **Add file → Upload files**，把这些文件拖进去（`.github` 目录可以在网页上用 "Create new file" 手动建，路径写 `.github/workflows/hot.yml`，内容复制过去）。

## 第 3 步：开 Pages + 启动定时任务

1. 仓库页面 → **Settings** → 左侧 **Pages**
2. Source 选 **Deploy from a branch**
3. Branch 选 **main** / 目录选 **/ (root)** → Save
4. 等 1–2 分钟，会出现访问地址：`https://github_gary.github.io/gary-hot/`
5. 点仓库顶部 **Actions** → 左侧选「热搜定时抓取」→ 右侧 **Run workflow** 手动跑一次，确认能出数据

**完成。** 之后每 30 分钟自动更新一次，手机打开就是最新的。

---

## 当前源的状态（2026-08-29 实测）

| 源 | 状态 | 说明 |
|---|---|---|
| 百度热搜 | ✅ 正常 | 20 条，链接为百度搜索结果页 |
| 华尔街见闻 | ✅ 正常 | 20 条金融快讯，**每条独立原文链接** |
| 微博热搜 | ✅ 正常 | 20 条，链接为话题页 |
| 知乎热榜 | ⚠️ 需登录态 | 官方 API 返回 401，脚本已降级跳过 |
| 财联社电报 | ⚠️ 接口变更 | 原接口 404，需更新路径 |

**脚本已内置两道防线**：
1. 单源失败不影响其他源
2. 某源本次被限 → 自动显示**上次成功结果**（页面不会开天窗）

---

## 本地手动跑一次

```bash
cd hotboard
python fetch_hot.py ../mobile/news.json
```

只依赖 Python 标准库，无需安装任何包。

---

## 常见问题

**Q：为什么有些源失败？**
A：热搜站普遍有反爬。境外 IP（GitHub Actions）可能比境内更容易被限。脚本会自动降级 + 用缓存兜底，不会白屏。

**Q：能加新源吗？**
A：能。在 `fetch_hot.py` 里加一个函数（返回 `[{'t':标题,'u':链接}]`），然后加到 `SOURCES` 列表即可。

**Q：更新频率能改吗？**
A：改 `.github/workflows/hot.yml` 里的 cron 表达式。注意是 **UTC 时间**，北京 = UTC+8。
