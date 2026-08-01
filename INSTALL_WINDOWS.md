# 老马智能股票盯盘助手 Windows 安装说明

## 本机安装

在 PowerShell 中进入软件目录后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_local.ps1 -IncludeCurrentData
```

安装结果：

- 程序目录：`%LOCALAPPDATA%\LaomaStockAssistant\app`
- 用户数据：`%APPDATA%\LaomaStockAssistant`
- 桌面快捷方式：`老马智能股票盯盘助手`

双击桌面快捷方式后，软件会自动：

1. 创建 Python 虚拟环境。
2. 安装依赖。
3. 启动本地服务。
4. 打开浏览器访问 `http://127.0.0.1:8788/?v=desktop`。

## 数据和隐私

每台电脑的数据都存放在当前 Windows 用户自己的 `%APPDATA%\LaomaStockAssistant` 下，包括：

- 登录账号数据库
- 每个用户的自选股和持仓
- Tushare Token
- 交易日志和推荐记录

分享给别人时，不要带上你的 `%APPDATA%\LaomaStockAssistant` 数据目录。

## 联网能力

软件启动后会通过当前电脑网络访问外部行情源，例如 Tushare、腾讯行情、东方财富等。电脑需要能正常访问互联网。

## 制作便携包

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_portable_windows.ps1
```

便携包目录会生成在：

```text
dist\LaomaStockAssistant
```

对外分享测试版时建议不要使用 `-IncludeCurrentData`，避免把自己的 Token、持仓和会员数据带出去。
