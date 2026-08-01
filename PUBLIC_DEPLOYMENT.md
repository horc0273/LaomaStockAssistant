# 老马智能股票盯盘助手：公网部署方案

这套部署适合云服务器 / VPS。应用本身是 FastAPI 后端 + 静态前端 + PostgreSQL + Redis，不建议只用静态网站托管。

## 推荐架构

公网用户 → HTTPS/Caddy → FastAPI 应用容器 → PostgreSQL / Redis 内网容器

- Caddy 自动申请和续期 HTTPS 证书。
- 只有 80/443 暴露到公网。
- App 的 8787 端口只在 Docker 内网给 Caddy 访问。
- PostgreSQL 和 Redis 不暴露公网。
- Cookie 使用 `COOKIE_SECURE=1`，只允许 HTTPS 登录态。

## 服务器要求

- 2 核 4G 起步，推荐 4 核 8G。
- Ubuntu 22.04 / Debian 12 / CentOS Stream 均可。
- 已安装 Docker 和 Docker Compose。
- 一个域名，例如 `stock.example.com`，并把 DNS A 记录指向服务器公网 IP。
- 安全组 / 防火墙开放 80 和 443。

## 首次部署

在服务器上进入项目根目录后执行：

```bash
cd deploy/public
cp .env.public.example .env.public
```

编辑 `.env.public`，至少填好：

```env
PUBLIC_DOMAIN=你的域名
ACME_EMAIL=你的邮箱
LAOMA_ADMIN_PASSWORD=一个强密码
POSTGRES_PASSWORD=另一个强密码
AI_API_KEY=你的 DeepSeek 或 OpenAI Compatible API Key
```

启动：

```bash
docker compose -f docker-compose.public.yml --env-file .env.public up -d --build
```

查看状态：

```bash
docker compose -f docker-compose.public.yml --env-file .env.public ps
docker compose -f docker-compose.public.yml --env-file .env.public logs -f app
docker compose -f docker-compose.public.yml --env-file .env.public logs -f caddy
```

浏览器访问：

```text
https://你的域名
```

登录账号默认是 `.env.public` 里的 `LAOMA_ADMIN_USER`，密码是 `LAOMA_ADMIN_PASSWORD`。

## 更新部署

把新代码同步到服务器后：

```bash
cd deploy/public
docker compose -f docker-compose.public.yml --env-file .env.public up -d --build
```

## 备份

PostgreSQL 保存自选股、提醒规则、分析报告等持久数据。建议定期备份：

```bash
docker compose -f docker-compose.public.yml --env-file .env.public exec postgres pg_dump -U laoma laoma_stock > laoma_stock_backup.sql
```

## 安全注意

1. 不要使用默认密码。公网部署时程序会拒绝默认管理员密码。
2. 不要把 `.env.public` 提交到 Git 或发给别人。
3. 服务器安全组只开放 80/443，SSH 建议限制你的固定 IP。
4. AI Key、Tushare Token 都放在环境变量，不要写进代码。
5. 如果只是自己使用，建议额外加 Cloudflare Access、Tailscale、Zero Trust 或 Nginx Basic Auth 做第二层保护。

## 临时公网试用方案

如果你暂时没有服务器，可以在本机运行桌面版，再用 Cloudflare Tunnel / Tailscale Funnel 做临时访问。但这只适合测试，不建议长期用于真实盯盘，因为电脑关机、网络波动、隧道失效都会影响服务。
