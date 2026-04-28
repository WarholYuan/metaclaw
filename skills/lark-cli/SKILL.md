---
name: lark-cli
description: >
  飞书 (Feishu/Lark) 官方 CLI 工具操作 skill。覆盖发消息、查日历、搜用户、透传 API 等所有飞书操作。
  触发场景：(1) 用户要求发送飞书消息，(2) 查询日程/日历，(3) 搜索飞书用户/部门，(4) 调用飞书开放 API。
metadata:
  author: metaclaw
  version: "1.0.0"
  requires:
    bins: ["lark-cli"]
---

# lark-cli Skill

## 工具定位

`lark-cli` 是飞书官方 Node.js 命令行工具。Agent 通过 `bash` 工具调用它，与飞书租户交互。

**认证配置路径：** `~/metaclaw-sandbox/.lark-cli/`（token、App ID 等由用户自行配置）。

## 常用命令速查

### 1. 发送消息 (IM)

```bash
lark-cli im message create --receive_id_type open_id --receive_id <USER_ID> --msg_type text --content '{"text":"你好"}'
```

支持的 `msg_type`：`text`、`post`、`image`、`file`、`interactive`。

**批量发送：** 先 `search-user` 获取用户列表，再循环发送（注意速率限制）。

### 2. 日历/日程 (Calendar)

```bash
lark-cli calendar event list --start_date <YYYY-MM-DD> --end_date <YYYY-MM-DD>
lark-cli calendar event detail --event_id <EVENT_ID>
```

获取今日日程：
```bash
lark-cli calendar event list --start_date $(date +%Y-%m-%d) --end_date $(date +%Y-%m-%d)
```

### 3. 搜索用户 (Contact)

```bash
lark-cli contact user search --query <KEYWORD> --limit 20
```

返回字段关注：`open_id`、`name`、`department`。

### 4. 原始 API 调用

```bash
lark-cli api GET /open-apis/contact/v3/users --query page_size=50
lark-cli api POST /open-apis/im/v1/messages --body '{"receive_id":"...","content":"..."}'
```

`METHOD` 支持：`GET`、`POST`、`PUT`、`DELETE`、`PATCH`。

## 认证说明

lark-cli 需要提前完成认证：

```bash
lark-cli auth login --app-id <APP_ID> --app-secret <APP_SECRET>
```

认证信息默认存储在 `~/.lark-cli/`。在 MetaClaw 沙盒中，建议将配置放在 `~/metaclaw-sandbox/.lark-cli/` 并通过 `LARK_CLI_CONFIG_DIR` 环境变量指向它，或在命令中通过 `--config-dir` 指定。

## 注意事项

1. **分页**：列表类 API 默认返回第一页。如需全量，检查响应中的 `has_more` 和 `page_token`，循环获取。
2. **输出格式**：lark-cli 默认输出 JSON。用 `| jq` 提取字段时，确保 jq 已安装。
3. **错误处理**：返回非 0 退出码时，stderr 包含飞书错误码和描述。常见错误：
   - `99991663` / `99991664`：token 过期，需重新 `auth login`
   - `10003`：参数非法，检查请求体 JSON 格式
4. **速率限制**：飞书开放平台有 QPS 限制。批量操作时建议串行或控制并发。
5. **用户 ID 类型**：飞书 API 支持 `open_id`、`user_id`、`union_id`、`email`。不同 API 要求的类型不同，调用前确认文档。
