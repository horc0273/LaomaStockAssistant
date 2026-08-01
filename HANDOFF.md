# HANDOFF：老马智能股票盯盘助手交接文档

写给下一个完全没有上下文的新会话。当前项目目录：

`C:\Users\GIGABYTE\Documents\Codex\2026-06-08\new-chat\work\ai-stock-platform\dist\LaomaStockAssistant-AI-Config-Source`

所有命令按本项目 AGENTS 约定尽量使用 `rtk` 前缀，例如：

```powershell
rtk python -m unittest .\tests\test_tushare_integration.py
rtk node -c static\app.js
```

## 1. 我们在做什么

我们在做一个内部/朋友可访问的 A 股智能盯盘与复盘系统，核心目标不是“花哨展示”，而是：

1. 数据源要真实、稳定、完整，尤其是日K、分时、K线、资金流。
2. AI 分析要走可配置外部模型，不依赖本地简陋规则。
3. 系统要能开放给朋友使用，因此需要登录、手机注册、权限隔离。
4. 将来可能接入券商账号做自动操作，但当前阶段必须先做“预检 + 人工确认”，不能直接自动实盘下单。
5. 用户非常重视量化资金/尾盘异动/资金趋势，因此“量化雷达 3.0”“多周期 K线 + 资金分析”是重要方向。
6. 项目已经部署到网站，用户希望配置和上传的数据持久化，不要每次重启/更新后重新输入。

## 2. 已经完成的主要功能

### 2.1 AI 模型配置扩展

前端 AI 配置已扩展多家 OpenAI-compatible 服务商：

- DeepSeek
- 硅基流动
- 智谱AI(GLM)
- 火山引擎 / 字节豆包
- 阿里云百炼
- Moonshot
- 腾讯混元
- 讯飞星火
- 零一万物
- MiniMax
- 小米MiMo / TokenPlan
- 腾讯云TokenHub
- OpenAI
- Azure OpenAI
- OpenRouter
- Ollama

相关文件：

- `static/index.html`
- `static/app.js`

已验证：

```powershell
rtk node -c static\app.js
```

### 2.2 手机注册 / 朋友试用入口

登录页新增了“手机注册 / 朋友试用”入口。注册后默认是 `member/trial`，手机号可登录。

相关后端：

- `app/auth_service.py`
  - `users` 表增加 `phone`
  - `register_by_phone`
  - `login` 支持 username 或 phone
- `app/main.py`
  - `POST /api/auth/register`

相关前端：

- `static/index.html`
  - `registerForm`
  - `registerPhone`
- `static/app.js`
  - `registerByPhone`

测试：

```powershell
rtk python -m unittest .\tests\test_registration_ai_presets.py
```

### 2.3 交易安全控制 / 自动操作前置闸门

已经做了“未来接券商账号自动操作”的安全底座，但真实自动实盘仍然关闭。

新增能力：

- 订单预检：可用资金、100股整数倍、价格、冷静期、个股风险。
- 情绪冷静期：急拉追高、恐慌割肉、尾盘异动时先冷静。
- 个股硬门槛：ST/退市风险硬阻断，流动性/估值异常提醒。
- 交易动作页可视化“交易安全控制”模块。

相关后端：

- `app/data_provider.py`
  - `update_manual_cash_available`
  - `current_cash_available`
  - `start_trade_cooldown`
  - `trade_cooldown_status`
  - `stock_compliance_gate`
  - `order_compliance_check`
  - `user_trading_action_queue` 内新增 `execution_controls`
- `app/main.py`
  - `POST /api/trading/precheck`
  - `POST /api/trading/cooldown`
  - `GET /api/trading/cooldown/{code}`
  - `GET /api/stocks/{code}/compliance-gate`

相关前端：

- `static/app.js`
  - 交易动作页渲染 `execution_controls`
- `static/styles.css`
  - `.execution-controls`
  - `.execution-control-card`

测试：

```powershell
rtk python -m unittest .\tests\test_execution_controls.py
```

### 2.4 可用资金可输入

之前用户指出“可用资金不能一直用截图/快照”。现在已有可输入并保存的机制：

- `POST /api/portfolio/cash`
- 前端 `portfolioCashInput`
- 后端 `update_user_manual_cash`

测试：

```powershell
rtk python -m unittest .\tests\test_portfolio_cash_override.py
```

### 2.5 决策融合面板

已经把次日预判、量化雷达、交易动作、数据源状态整合成一个“决策融合”入口。

相关后端：

- `DemoDataProvider.user_decision_fusion(user)`
- `GET /api/decision/fusion`

相关前端：

- `decisionFusionPanel`
- `renderDecisionFusion`

测试：

```powershell
rtk python -m unittest .\tests\test_decision_fusion.py
```

### 2.6 Tushare 数据源接入与持久化配置

这是最近刚做的一版，解决用户反馈：

> 日K、分时、K线数据都有问题；已经买了 Tushare；部署网站后不想每次重新输入数据。

已完成：

- Tushare token 可保存到服务器数据目录：
  - `data/tushare_token.txt`
- 后端配置接口：
  - `GET /api/tushare/config`
  - `POST /api/tushare/config`
- 前端“智能选股 / 数据健康”区域新增 `Tushare 数据源配置` 卡片，可由管理员输入一次 token。
- 日K优先走 Tushare `daily`。
- 资金流优先走 Tushare `moneyflow`。
- 分时如果东方财富不可用，会尝试 Tushare `stk_mins` 分钟线。
- 如果 Tushare 账号没有分钟线权限，系统会明确提示不可用，不再用假数据糊弄。

相关文件：

- `app/tushare_service.py`
  - `save_token`
  - `config_status`
  - `minute`
- `app/data_provider.py`
  - `stock_minute_chart` 增加 Tushare `stk_mins` fallback
  - `stock_kline_chart_tushare`
  - `stock_fund_chart_tushare`
- `app/main.py`
  - `TushareConfigPayload`
  - `/api/tushare/config`
- `static/app.js`
  - `Tushare 数据源配置` UI
  - `saveTushareToken`
- `static/styles.css`
  - `.tushare-config-card`
  - `.tushare-config-row`
- `tests/test_tushare_integration.py`

测试：

```powershell
rtk python -m unittest .\tests\test_tushare_integration.py
rtk python -m unittest .\tests\test_technical_fund_analysis.py
```

### 2.7 最新已打包版本

最新打包文件：

`C:\Users\GIGABYTE\Documents\Codex\2026-06-08\new-chat\work\ai-stock-platform\dist\LaomaStockAssistant-Server-1.6.6-TushareDataCompleteness.zip`

上一版：

`LaomaStockAssistant-Server-1.6.5-ExecutionControls-PhoneAI.zip`

## 3. 当前卡在哪 / 还没彻底解决什么

### 3.1 真实 Tushare Token 还没在本地会话里配置

用户截图里 token 是脱敏的，不能也不应该从截图里抄。

现在正确方式是：

1. 用户部署新版包。
2. 用管理员登录。
3. 进入“智能选股 / 数据健康”。
4. 在 `Tushare 数据源配置` 中粘贴真实 token。
5. 保存后会写入服务器 `data/tushare_token.txt`。

如果用户愿意在当前本地环境测试，也可以直接设置：

```powershell
$env:TUSHARE_TOKEN="真实token"
```

但部署网站最好用后台保存，不要每次靠环境变量。

### 3.2 分钟线权限取决于 Tushare 账号权益

我们已经接了 `stk_mins`，但 Tushare 账号是否能取到分钟线，取决于用户的积分/权限。

如果报错类似“权限不足/接口权限不足/积分不足”，这不是代码 bug，而是 Tushare 权限问题。

应对策略：

- 有权限：使用 Tushare 分钟线。
- 没权限：继续用东方财富实时分时；东方财富失败时明确提示不可用。
- 后续可以再接腾讯/新浪/mootdx 做分时多源兜底。

### 3.3 网站部署后的数据持久化要确认服务器数据目录

当前持久化路径由 `LAOMA_STOCK_DATA_DIR` 控制。

如果没有设置，代码会用默认数据目录。部署时必须确认：

- `data/tushare_token.txt` 是否在服务器持久目录。
- Docker/服务器重启后这个目录是否会保留。
- 如果用容器，必须挂载 volume，否则 token/用户状态/自选股仍可能丢。

这是下一步必须重点检查的点。

### 3.4 K线/资金分析还需要实盘验证

目前单元测试验证的是链路和 fallback 行为；还没有用真实 token 对真实股票做完整 live 验证。

下一会话如果用户给 token 或已部署好，应做 live check：

```powershell
rtk python -c "from app.data_provider import DemoDataProvider; p=DemoDataProvider(); print(p.tushare.config_status()); print(p.stock_kline_chart('002463.SZ')['source']); print(p.stock_minute_chart('002463.SZ')['source']); print(p.stock_fund_chart('002463.SZ')['source'])"
```

如需联网且沙箱限制，请按工具要求申请网络/外部权限。

## 4. 下一步计划

建议下一会话按这个顺序做，不要跳：

### 第一步：确认部署数据目录持久化

目标：保证网站重启、重新上传包后，不丢：

- Tushare token
- 用户账号/手机号
- 自选股
- 持仓成本/数量
- 可用资金
- 提醒规则
- AI配置
- 复盘历史

需要检查：

- `LAOMA_STOCK_DATA_DIR`
- `DATABASE_URL`
- Docker volume / 服务器目录挂载
- PostgreSQL 是否真的启用，还是 fallback 到 SQLite

相关文件：

- `app/infrastructure.py`
- `app/auth_service.py`
- `app/data_provider.py`
- `docker-compose.yml`
- `PUBLIC_DEPLOYMENT.md`

### 第二步：真实 token 联调

保存 token 后，验证：

- `/api/tushare/status`
- `/api/tushare/config`
- `/api/stocks/002463.SZ/tushare`
- `/api/stocks/002463.SZ/chart?type=kline`
- `/api/stocks/002463.SZ/chart?type=minute`
- `/api/stocks/002463.SZ/chart?type=fund`
- `/api/stocks/002463.SZ/technical-fund-analysis`

重点看：

- `is_real`
- `source`
- `items.length`
- `message`

### 第三步：多源分时兜底增强

如果 Tushare `stk_mins` 权限不足，应接入更多分时源：

1. 东方财富 `trends2`：已接。
2. Tushare `stk_mins`：已接。
3. 腾讯实时/分时：建议补。
4. 新浪分时：可补。
5. mootdx：可选，但部署服务器上 TCP/端口/稳定性要小心。

目标：分时至少 2-3 个源，不让用户再看到“不可用/降级”。

### 第四步：K线分析深做

用户明确说“量化3.0必须做”，K线不是为了画图，而是为了判断资金/量化行为。

下一步可做：

- 日K/周K/月K多周期融合。
- 分时尾盘 14:30-14:57 异动识别。
- 量价背离、放量滞涨、冲高回落、急跌承接。
- 资金流与 K线同屏分析。
- “量化嫌疑分”解释可视化。

### 第五步：券商账号/自动操作架构设计

不要直接接实盘自动下单。必须先设计：

- 券商账号授权与加密保存。
- 只读持仓同步。
- 模拟交易。
- 预检。
- 人工确认。
- 小额灰度。
- 风控限额。
- 撤单/异常处理。
- 全量操作日志。

当前系统已经有预检/冷静期/人工确认基础，下一步应先接“只读持仓同步”，不要先接“自动买卖”。

## 5. 绝对不要再踩的坑

### 5.1 不要用假数据冒充真实行情

用户非常敏感，也非常在意数据真实性。

如果接口不可用，必须明确：

- `is_real: false`
- `source`
- `message`
- 降级原因

不要为了界面好看生成模拟分时/K线。

### 5.2 不要把“接入接口”说成“已验证真实可用”

接入代码通过测试，只代表链路存在。真实可用必须用真实 token、真实网络、真实股票验证。

回答时区分：

- 已实现
- 已单元测试
- 已本地真实请求验证
- 已服务器部署验证

### 5.3 不要从截图抄 token

截图里的 Tushare token 是脱敏的；即使完整，也不要在对话里明文传播。

正确做法是让用户在系统后台粘贴保存，或在服务器环境变量/密钥管理里配置。

### 5.4 不要让部署包覆盖用户数据

用户已经强调“不想每次重新输入”。后续打包/部署要避免覆盖：

- `data/`
- SQLite 数据库
- token 文件
- 用户状态 JSON
- AI配置

如果必须更新代码，尽量只替换代码目录，保留数据目录或使用外部 volume。

### 5.5 不要直接开放实盘自动交易

用户想以后通过软件连接账号自动操作，但当前必须坚持：

- 先只读。
- 再模拟。
- 再预检。
- 再人工确认。
- 最后才考虑小额实盘自动。

任何自动买卖都必须有：

- 风控上限
- 黑名单
- 交易时段限制
- 冷静期
- 日志
- 异常停止

### 5.6 不要把 Windows PowerShell 乱码误判成源码乱码

很多 `Get-Content` 输出看起来是乱码，但源码实际是 UTF-8 正常中文。

要确认中文内容，用：

```powershell
rtk python -c "from pathlib import Path; print(Path('static/index.html').read_text(encoding='utf-8')[:200])"
```

### 5.7 不要用普通 PowerShell 变量直接进 JSON/命令字符串

之前打包时 `$root` 等变量被外层吃掉，导致命令变形。

在 `rtk powershell -Command` 里用变量，要转义：

```powershell
`$root = Resolve-Path '.'
```

### 5.8 打包不要把内部 build/dist/cache/log 全塞进去

之前 `Compress-Archive` 复制整个目录导致超时，后来改用：

```powershell
tar -a -cf $zip --exclude='LaomaStockAssistant-AI-Config-Source/build' --exclude='LaomaStockAssistant-AI-Config-Source/dist' --exclude='LaomaStockAssistant-AI-Config-Source/__pycache__' --exclude='LaomaStockAssistant-AI-Config-Source/.pytest_cache' --exclude='*.log' -C $parent 'LaomaStockAssistant-AI-Config-Source'
```

注意 PowerShell 变量要转义。

### 5.9 测试里 Windows sqlite 可能有 ResourceWarning

多组测试会出现：

`ResourceWarning: unclosed database in <sqlite3.Connection object ...>`

目前测试结果是 OK，警告主要来自 Windows 临时目录清理和 sqlite 句柄回收，不影响功能判断。

但如果出现 `PermissionError` 删除 `auth.sqlite`，测试 tearDown 需要：

- `client.close()`
- 清空 provider/auth_service/client 引用
- `gc.collect()`

相关测试已这样处理：

- `tests/test_execution_controls.py`
- `tests/test_registration_ai_presets.py`
- `tests/test_tushare_integration.py`

### 5.10 不要忽略用户截图里的“看不到”

用户经常会说“没看到你说的那些”。所以新增后端功能时，最好同时加前端可视入口。

例如这次交易安全控制不仅有 API，也加了交易动作页的可视模块。

## 6. 重要命令清单

常用验证：

```powershell
rtk python -m py_compile app\tushare_service.py app\data_provider.py app\main.py
rtk node -c static\app.js
rtk python -m unittest .\tests\test_tushare_integration.py
rtk python -m unittest .\tests\test_technical_fund_analysis.py
rtk python -m unittest .\tests\test_mobile_dashboard_frontend.py
rtk python -m unittest .\tests\test_execution_controls.py .\tests\test_registration_ai_presets.py .\tests\test_decision_fusion.py .\tests\test_portfolio_cash_override.py
rtk python -m unittest .\tests\test_ai_research_report.py
```

打包参考：

```powershell
rtk powershell -NoProfile -Command "`$root = Resolve-Path '.'; `$parent = Split-Path `$root -Parent; `$zip = Join-Path `$parent 'LaomaStockAssistant-Server-1.6.7-YourFeature.zip'; if (Test-Path `$zip) { Remove-Item -LiteralPath `$zip -Force }; tar -a -cf `$zip --exclude='LaomaStockAssistant-AI-Config-Source/build' --exclude='LaomaStockAssistant-AI-Config-Source/dist' --exclude='LaomaStockAssistant-AI-Config-Source/__pycache__' --exclude='LaomaStockAssistant-AI-Config-Source/.pytest_cache' --exclude='*.log' -C `$parent 'LaomaStockAssistant-AI-Config-Source'; Get-Item `$zip | Select-Object FullName,Length,LastWriteTime | Format-List"
```

## 7. 当前建议给用户的下一句话

如果新会话接上，建议先这样说：

> 我先不急着继续加功能，先帮你把服务器上的 Tushare Token 保存和数据目录持久化确认一下。因为现在代码已经支持 Tushare 持久化配置，真正要避免“每次重新输入”和“K线分时不可用”，关键是服务器 `data/` 目录要持久、token 要保存进去，然后用真实 token 跑一次日K/分时/资金接口验证。

这句话会比较贴合用户当前最关心的点。
