# 内部 AI 股票盯盘助手 MVP

这是从原型升级出来的第一版可运行工程。

## 当前能力

- FastAPI 后端。
- 前端工作台页面。
- 自选股搜索、添加、删除。
- 市场行情概览。
- 研究中心候选评分。
- 2060战法、背离、均线、量价、资金模型的结构化评分。
- WebSocket 实时行情更新。
- 每只自选股 AI 分析。
- 未配置 AI API 时使用本地规则引擎。
- 配置 AI API 后使用 OpenAI/DeepSeek 兼容接口生成完整报告和动作建议。

行情按真实系统分层，Tushare、东方财富、腾讯为主源，AKShare 可作为可选交叉验证和备用历史行情源：

- `data_provider.py`：数据源适配层，后续替换真实行情接口。
- `quant_engine.py`：量化模型和评分。
- `main.py`：API、WebSocket、静态页面托管。
- `backtest_service.py`：无未来函数的策略回测、费用/滑点、最大回撤和参数扫描。
- `akshare_service.py`：可选 AKShare 数据适配器。

## 运行

```powershell
cd C:\Users\GIGABYTE\Documents\Codex\2026-06-08\new-chat\work\ai-stock-platform
python -m uvicorn app.main:app --host 127.0.0.1 --port 8787
```

打开：

```text
http://127.0.0.1:8787
```

## AI API 配置

不配置时默认使用本地规则引擎。

管理员登录后，可以直接点击左侧“AI网关”打开模型配置。支持 DeepSeek、OpenAI 和其他 OpenAI Chat Completions 兼容接口；可测试连接、保存并立即切换模型。配置保存在本机 `%APPDATA%\LaomaStockAssistant\ai_config.json`，普通会员只能查看当前使用的模型，不能修改密钥。

DeepSeek 示例：

```powershell
$env:AI_API_KEY="你的DeepSeek API Key"
$env:AI_BASE_URL="https://api.deepseek.com/v1"
$env:AI_MODEL="deepseek-chat"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8787
```

OpenAI 兼容接口示例：

```powershell
$env:AI_API_KEY="你的API Key"
$env:AI_BASE_URL="https://api.openai.com/v1"
$env:AI_MODEL="gpt-4.1-mini"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8787
```

AI 分析会输出：

- BUY / HOLD / REDUCE / SELL / WATCH 动作建议。
- 置信度。
- 仓位建议。
- 买入区。
- 减仓/卖出区。
- 止损/失效条件。
- 下一触发条件。

## 下一步

- 接入真实 A 股行情源。
- 接入公告、研报、资金流。
- PostgreSQL 持久化自选股、提醒规则、分析报告。
- Redis 缓存实时行情。
- 登录、权限、内部部署。
