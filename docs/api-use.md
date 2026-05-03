# API 可用性验证文档

## 验证时间
2026-05-03 17:54

## 验证内容
- openrouter API（qwen/qwen-turbo 模型）
- openrouter API（qwen/qwen-vl-plus 模型）
- tavily API

## 验证方式
- 通过 curl 命令，使用 .env 文件中的 API Key 和模型名称，分别对 openrouter 两个模型和 tavily API 进行接口请求。

### Raw command

#### openrouter qwen/qwen-turbo
```
curl -s -H "Authorization: Bearer $OPENROUTER_API_KEY" -H "HTTP-Referer: https://openrouter.ai" -H "X-Title: Test" -H "Content-Type: application/json" -d '{"model": "$OPENROUTER_MODEL", "messages": [{"role": "user", "content": "ping"}]}' $OPENROUTER_BASE_URL/chat/completions
```

#### openrouter qwen/qwen-vl-plus
```
curl -s -H "Authorization: Bearer $OPENROUTER_API_KEY" -H "HTTP-Referer: https://openrouter.ai" -H "X-Title: Test" -H "Content-Type: application/json" -d '{"model": "$OPENROUTER_IMAGE_MODEL", "messages": [{"role": "user", "content": "ping"}]}' $OPENROUTER_BASE_URL/chat/completions
```

#### tavily
```
curl -s -H "Authorization: Bearer $TAVILY_API_KEY" "https://api.tavily.com/v1/search?q=ping"
```

## 验证结果
- openrouter API（qwen/qwen-turbo）返回正常回复，接口可用。
- openrouter API（qwen/qwen-vl-plus）返回正常回复，接口可用。
- tavily API 返回正常，无报错，接口可用。

## 结论
上述 API 及 openrouter 的两个模型均可正常使用。