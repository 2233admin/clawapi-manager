# Changelog

## v1.2.0 (2026-03-03)

### 新增功能
- ✅ 协议识别与管理
  - 支持 anthropic-messages、openai-chat、openai-compatible
  - 自动读取现有配置中的 api 字段
  - 显示 provider 的协议类型
  - 支持手动设置协议

- ✅ 故障排查指南
  - 常见错误码对照表（401/403/404/429/500/503）
  - 详细的排查步骤和解决方案
  - 500/503 错误详解
  - 自动 Fallback 配置建议

- ✅ 配置修复功能
  - 自动检测空的 provider 配置
  - 一键删除损坏的配置
  - 从备份恢复配置
  - 配置验证

### 改进
- 📊 Provider 列表显示协议类型
- 🔧 添加 provider 时支持指定协议
- 📝 完善文档（TROUBLESHOOTING.md、HIGHLIGHTS.md）
- 🛡️ 增强配置安全性

### 修复
- 🐛 修复空 provider 导致的验证错误
- 🐛 修复协议类型不匹配的问题

---

## v1.1.0 (2026-03-03)

### 新增功能
- ✅ Textual TUI（完整交互界面）
- ✅ Rich 菜单（受限终端）
- ✅ 对话式接口（QQ/飞书）
- ✅ 智能环境检测
- ✅ Channel 管理

### 核心功能
- 📦 Models 管理（Providers、API keys、Primary & Fallback）
- 🔗 Channels 管理（QQ、企业微信、飞书、钉钉等）
- 🎯 Skills 管理（查看已安装 skills）
- 🌐 多界面支持（TUI、Rich、CLI、对话式）

---

## v1.0.0 (2026-03-02)

### 初始版本
- ✅ 基础配置管理
- ✅ Provider 管理
- ✅ Model 管理
- ✅ 自动备份
- ✅ API key 脱敏
