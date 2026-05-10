# leo-imagine

MCP server for image generation via Replicate Flux Schnell.

## 部署步骤

### 1. GitHub
新建仓库 `leo-imagine`，上传 `main.py` 和 `requirements.txt`。

### 2. Render
- New → Web Service → 连接仓库
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Environment Variables: `REPLICATE_TOKEN` = 你的token

### 3. Claude MCP
服务部署后，在 Claude.ai → Settings → Connectors 添加：
- Name: leo-imagine
- URL: https://你的服务名.onrender.com/mcp

## Tools
- `generate_image(prompt, aspect_ratio)` — 生成图片，返回URL
- `get_status()` — 检查服务状态
