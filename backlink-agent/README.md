# ToonTones Backlink Agent

Automated + semi-automated backlink submission for toontones.net.

## 结构

```
backlink-agent/
├── sites.json              # 目标站列表 + 提交状态（唯一真相来源）
├── templates/
│   ├── short.txt           # 100字以内描述
│   ├── long.txt            # 完整介绍
│   ├── reddit_webgames.txt # Reddit r/WebGames 专用帖子
│   └── medium_article_outline.txt
├── submitters/
│   ├── form_submit.py      # Playwright 填表（无需登录）
│   └── reddit_post.py      # Reddit 官方 API (PRAW)
├── run.py                  # 主入口
└── .env.example            # Reddit 凭据模板
```

## 安全边界

| 方案 | 安全？ |
|---|---|
| Playwright 填表（form 类型）| ✅ 无需登录，最安全 |
| Reddit 官方 PRAW API | ✅ OAuth2，官方支持 |
| Cookie 劫持模拟登录 | ❌ 封号风险，不做 |
| 批量一次性提交几十个 | ❌ Google 降权，不做 |

## 使用方法

```bash
# 安装依赖
pip install playwright praw python-dotenv
playwright install chromium

# 查看进度
python run.py --status

# 提交下一批（最多3个 form 类型站）
python run.py --next

# 预览不提交
python run.py --next --dry-run

# 发 Reddit 帖（每次只发1个子版）
python run.py --reddit

# 查看需要手动操作的站
python run.py --manual
```

## Reddit 配置（一次性）

1. 去 https://www.reddit.com/prefs/apps 创建 app（选 script 类型）
2. 复制 client_id / client_secret
3. 复制 `.env.example` 为 `.env` 并填入凭据

## 节奏建议

- 每次运行 `--next` 提交 1-3 个，**每周跑 2-3 次**
- Reddit 每个子版至少间隔 **7 天**
- 不要同一天提交超过 5 个，Google 看到批量外链会降权
- 优先顺序：form → reddit_api → manual/web2

## 进度追踪

所有提交状态记录在 `sites.json` 的 `status` 和 `submitted_at` 字段。
运行 `python run.py --status` 随时查看进度。
