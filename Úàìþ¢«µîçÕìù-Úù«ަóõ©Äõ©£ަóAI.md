# 老马股票助手 — 问财 & 东财妙想AI 配置指南

> 本文档指导您配置和使用新接入的 **问财智能选股** 和 **东方财富妙想AI** 两大能力模块。

---

## 一、问财（iWencai）配置

### 1.1 特点说明
- **无需 API Key**，直接调用 iWencai 公开接口
- 支持**自然语言选股**（如"近5日涨幅超过10%的科技股"）
- 支持**条件组合筛选**（多条件 AND 组合）

### 1.2 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wencai/status` | 查看问财服务状态 |
| POST | `/api/wencai/query` | 自然语言问答/选股 |
| POST | `/api/wencai/screen` | 条件筛选选股 |

### 1.3 请求示例

**自然语言选股：**
```bash
curl -X POST http://localhost:8000/api/wencai/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{"question": "今日涨停的股票有哪些"}'
```

**条件筛选：**
```bash
curl -X POST http://localhost:8000/api/wencai/screen \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{"conditions": ["近5日涨幅大于10%", "市值大于100亿", "市盈率小于30"]}'
```

---

## 二、东方财富妙想AI 配置

### 2.1 获取 API Key

东财妙想AI 需要配置 API Key 才能使用，获取方式：

1. **访问东财AI官网**：https://ai.eastmoney.com/mxClaw
2. **登录您的东方财富账号**
3. **进入「开发者中心」或「API管理」**
4. **创建应用，获取 `API Key`**
5. **（可选）获取 `qgqp_b_id` Cookie** — 部分高级功能需要此 Cookie

> 如果您已有 go-stock 软件，可以直接复用其配置面板中的 Key。

### 2.2 配置方式（三选一）

#### 方式一：环境变量（推荐，生产环境）

在启动服务前设置环境变量：

```bash
# Windows PowerShell
$env:EASTMONEY_AI_API_KEY = "your-api-key-here"
$env:EASTMONEY_QGQP_B_ID = "your-cookie-value"

# Windows CMD
set EASTMONEY_AI_API_KEY=your-api-key-here
set EASTMONEY_QGQP_B_ID=your-cookie-value

# Linux/macOS
export EASTMONEY_AI_API_KEY="your-api-key-here"
export EASTMONEY_QGQP_B_ID="your-cookie-value"
```

#### 方式二：Token 文件（适合本地开发）

在数据目录下创建两个文件：

```
<data_dir>/
  ├── eastmoney_ai_api_key.txt    # 写入 API Key
  └── eastmoney_qgqp_b_id.txt     # 写入 Cookie（可选）
```

#### 方式三：代码中直接传入（开发调试）

```python
from app.eastmoney_ai_service import EastMoneyAIService

service = EastMoneyAIService(
    api_key="your-api-key",
    qgqp_b_id="your-cookie"
)
```

### 2.3 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/eastmoney-ai/status` | 查看东财AI服务状态 |
| POST | `/api/eastmoney-ai/hotspot` | AI 热点发现（早盘简报） |
| POST | `/api/eastmoney-ai/stock-analysis` | 个股AI深度分析 |
| POST | `/api/eastmoney-ai/performance` | 个股业绩点评 |
| POST | `/api/eastmoney-ai/sentiment` | 市场情绪分析 |
| POST | `/api/eastmoney-ai/chat` | 通用AI问答 |

### 2.4 请求示例

**查看状态：**
```bash
curl http://localhost:8000/api/eastmoney-ai/status \
  -H "Authorization: Bearer <your_token>"
```

**热点发现：**
```bash
curl -X POST http://localhost:8000/api/eastmoney-ai/hotspot \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{"question": "今日热点板块有哪些"}'
```

**个股分析：**
```bash
curl -X POST http://localhost:8000/api/eastmoney-ai/stock-analysis \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{"code": "000001"}'
```

**业绩点评：**
```bash
curl -X POST http://localhost:8000/api/eastmoney-ai/performance \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{"code": "600519"}'
```

**市场情绪：**
```bash
curl -X POST http://localhost:8000/api/eastmoney-ai/sentiment \
  -H "Authorization: Bearer <your_token>"
```

**通用问答：**
```bash
curl -X POST http://localhost:8000/api/eastmoney-ai/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{
    "question": "分析一下当前新能源板块的投资机会",
    "code": "300750",
    "name": "宁德时代"
  }'
```

---

## 三、快速验证清单

启动服务后，按以下顺序验证：

1. **问财状态** — `GET /api/wencai/status` → 应返回 `enabled: true`
2. **东财AI状态** — `GET /api/eastmoney-ai/status` → 配置Key后应返回 `enabled: true`
3. **问财选股** — `POST /api/wencai/query` → 输入自然语言测试
4. **东财热点** — `POST /api/eastmoney-ai/hotspot` → 获取今日热点
5. **个股分析** — `POST /api/eastmoney-ai/stock-analysis` → 输入任意股票代码

---

## 四、常见问题

### Q1: 东财AI返回 `em_ai_not_configured`
**原因**：API Key 未配置  
**解决**：按上方「配置方式」设置环境变量或创建 token 文件

### Q2: 东财AI返回 `em_ai_auth_failed`
**原因**：API Key 无效或已过期  
**解决**：登录 https://ai.eastmoney.com/mxClaw 重新获取

### Q3: 东财AI返回 `em_ai_forbidden`
**原因**：`qgqp_b_id` Cookie 失效  
**解决**：重新登录东财网页版，从浏览器开发者工具中复制新的 `qgqp_b_id`

### Q4: 问财接口无响应
**原因**：iWencai 服务端限流或网络问题  
**解决**：稍后重试，或检查网络连接

---

## 五、前端集成建议

建议在老马助手前端新增两个快捷入口：

1. **「智能选股」入口** — 调用问财接口，支持自然语言输入
2. **「AI研报」入口** — 调用东财AI接口，自动分析持仓个股和热点板块

数据层已通过 `provider.wencai` 和 `provider.eastmoney_ai` 暴露，前端可直接复用现有请求封装。

---

> 文档版本：v1.0 | 生成时间：2026-07-31
