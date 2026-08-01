# 内部部署

1. 复制 `.env.example` 为 `.env`。
2. 必须修改 `POSTGRES_PASSWORD`、`LAOMA_ADMIN_PASSWORD`，并填写需要的 AI Key / Tushare Token。
3. 执行 `docker compose up -d --build`。
4. 内网访问 `http://服务器IP:8787`。正式环境建议在前面配置 HTTPS 反向代理，并把 `COOKIE_SECURE` 设为 `1`。

运行状态可由管理员访问 `/api/system/infrastructure` 查看。PostgreSQL 保存自选股、提醒规则和 AI 报告；Redis 缓存行情、公告、研报和资金流。桌面版没有连接这些服务时会自动使用 SQLite 与进程内缓存。
