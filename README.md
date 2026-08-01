# 老马股票助手（LaomaStockAssistant）

> 🎯 **内部量化工作台** — 面向 A 股投资者的智能盯盘、选股、复盘一体化工具
>
> ⚠️ **风险提示**：本工具仅供研究学习，不构成任何投资建议。股市有风险，入市需谨慎。

---

## ✨ 功能概览

| 模块 | 说明 |
|------|------|
| 📊 **今日工作台** | 大盘情绪、账户概览、AI 盘中判断、实时事件流 |
| 🔍 **智能选股** | 形态选股（放量突破/跳空/反包）、自然语言指标选股、推荐验证 |
| 🤖 **AI 工具** | 同花顺问财自然语言选股、东方财富妙想 AI（热点/个股分析/问答） |
| 📈 **市场行情** | 全球股指、板块强弱、资金流、龙虎榜、市场宽度热力图 |
| ⚡ **异动监控** | 火箭发射、打开涨停、封跌停、大笔买卖等实时异动 |
| 📝 **复盘中心** | 每日市场情绪、自选股重点、观察池候选、历史复盘记录 |
| 🎯 **交易动作** | 市场闸门、突破复核、EA 模拟盘、交易日志 |
| 🔬 **研究中心** | 产业链拆解、系统审计、量化升级路线、多智能体分歧审查 |
| 👤 **会员管理** | 多级会员体系、AI 模型个人配置、权限隔离 |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Windows / macOS / Linux

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/yourname/LaomaStockAssistant.git
cd LaomaStockAssistant

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 4. 启动服务
python desktop_launcher.py
```

服务启动后自动打开浏览器，访问 `http://127.0.0.1:8788`

---

## 🔑 数据源配置

### 问财智能选股（iwencai.com）

1. 用浏览器登录 [iwencai.com](https://www.iwencai.com)
2. 打开开发者工具 → Application → Cookies → 找到 `hexin-v`
3. 将值写入 `wencai_hexinv.txt` 文件

### 东方财富妙想 AI

1. 访问 [ai.eastmoney.com](https://ai.eastmoney.com)
2. 获取 API Key 和 Cookie
3. 分别写入 `eastmoney_api_key.txt` 和 `eastmoney_cookie.txt`

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                      前端层 (Web)                         │
│  HTML + CSS + Vanilla JS    响应式适配 PC + 移动端        │
├─────────────────────────────────────────────────────────┤
│                      API 层 (FastAPI)                     │
│  行情数据 / 选股扫描 / AI 分析 / 会员管理 / 风控引擎        │
├─────────────────────────────────────────────────────────┤
│                      数据层                              │
│  AKShare / Tushare / 东方财富 / 问财 / 东财 AI           │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 项目结构

```
LaomaStockAssistant/
├── app/                    ← 后端核心
│   ├── main.py            ← FastAPI 入口
│   ├── data_provider.py   ← 数据提供层
│   ├── wencai_service.py  ← 问财服务
│   ├── eastmoney_ai_service.py  ← 东财 AI 服务
│   ├── screener_service.py      ← 选股引擎
│   ├── quant_engine.py          ← 量化引擎
│   ├── risk_engine.py           ← 风控引擎
│   └── ...
├── static/                 ← 前端资源
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── data/                   ← 本地数据缓存
├── tests/                  ← 测试用例
├── requirements.txt
├── desktop_launcher.py     ← 桌面启动器
└── docker-compose.yml      ← Docker 部署
```

---

## 🛡️ 安全与隐私

- 🔒 API Key 仅保存在本地配置文件，不上传服务器
- 🔒 会员数据使用 PostgreSQL 本地存储
- 🔒 交易相关操作仅模拟，不连接真实券商

---

## 📜 开源协议

[MIT License](LICENSE)

---

## 🤝 贡献

欢迎 Issue 和 PR！详见 [CONTRIBUTING.md](CONTRIBUTING.md)

---

> **Made with ❤️ by 老马** — 长沙县果园镇 · 花果虾品牌
