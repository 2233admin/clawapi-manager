# 故障排查指南

## 常见错误码

错误码因提供商不同可能略有出入，仅供参考。

| 错误码 | 原因 | 解决方案 |
|--------|------|----------|
| **401** | API Key 不正确 | 前往模型提供商检查写入的 API Key 是否正确 |
| **429/500** | 余额不足 | 充钱或检查 API Key 是否正确 |
| **rate_limit** | 速率限制 | 更换提供商，或联系提供商获取更大配额 |
| **404** | Base URL 不对 | 查看提供商文档寻找兼容 OpenAI Chat Completions API 或 Anthropic Messages API 的 base URL 地址 |
| **403** | 该模型不支持此服务器地域 | 更换服务器地域为模型支持的地域或更换模型 |

---

## 名词释义

- **RPM (Requests Per Minute)**：每分钟请求数
- **TPM (Tokens Per Minute)**：每分钟处理的 Tokens 数量

---

## 常见问题

### 1. 模型回复慢（响应慢）

**原因：**
- 若您选择的轻量应用服务器为境外地域且使用境内通道/模型提供商，可能会因跨境网络原因导致延迟较高
- 若您选择深度思考模型，可能因上下文过多导致模型思考时间过长

**解决方案：**
- 更换服务器地域
- 推荐您选择非思考模型/快思考模型进行替代

---

### 2. Token 消耗过快

**原因：**
OpenClaw 在调用模型时会携带较多上下文信息，以保证任务连贯性与准确性，因此 Token 消耗可能较高。

**解决方案：**
- 建议在使用时关注 Token 用量与计费情况
- 使用 ClawAPI Manager 的智能路由功能，自动选择免费/低成本模型
- 配置 Fallback 链，优先使用低成本模型

---

## ClawAPI Manager 相关问题

### 1. 协议不匹配

**症状：**
- 404 错误
- 模型无法调用

**原因：**
- Provider 的协议类型（`api` 字段）配置错误
- 第三方 API 中转服务协议不匹配

**解决方案：**
```bash
# 查看当前协议
./clawapi providers

# 设置正确的协议
# Anthropic Messages API
python3 -c "from clawapi_helper import *; print(set_protocol_interactive('xart', 'anthropic-messages'))"

# OpenAI Chat Completions
python3 -c "from clawapi_helper import *; print(set_protocol_interactive('openai', 'openai-chat'))"

# OpenAI Compatible (默认)
python3 -c "from clawapi_helper import *; print(set_protocol_interactive('provider', 'openai-compatible'))"
```

---

### 2. 配置文件损坏

**症状：**
- ClawAPI Manager 无法启动
- JSON 解析错误

**解决方案：**
```bash
# 查看备份
ls ~/.openclaw/backups/

# 恢复备份
cp ~/.openclaw/backups/openclaw_20260303_020000.json ~/.openclaw/openclaw.json

# 重启 Gateway
openclaw gateway restart
```

---

### 3. API Key 失效

**症状：**
- 401 错误
- 认证失败

**解决方案：**
```bash
# 更新 API Key
python3 -c "from clawapi_helper import *; manager.update_api_key('provider_name', 'new_key')"

# 或使用 TUI
python3 clawapi-tui.py
# 进入 Models 标签 → 选择 provider → Update Key
```

---

## 获取帮助

- GitHub Issues: https://github.com/2233admin/clawapi-manager/issues
- OpenClaw Discord: https://discord.com/invite/clawd
- ClawHub: https://clawhub.com
