"""
leo-imagine: MCP server for image generation via Replicate API
架构：FastAPI + MCP协议 + Replicate Flux Schnell
"""

import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP

# ── 1. 读取环境变量 ──────────────────────────────────────────
# Replicate token 存在 Render 的环境变量里，不写死在代码中（安全）
REPLICATE_TOKEN = os.environ.get("REPLICATE_TOKEN", "")

# ── 2. 创建 MCP 实例 ─────────────────────────────────────────
# FastMCP 帮我们处理所有 MCP 协议细节
# 我们只需要定义"工具"就行
mcp = FastMCP("leo-imagine")

# ── 3. 定义工具：生成图片 ────────────────────────────────────
@mcp.tool()
async def generate_image(
    prompt: str,
    aspect_ratio: str = "1:1"
) -> str:
    """
    Generate an image using Flux Schnell on Replicate.
    
    Args:
        prompt: Image description in any language
        aspect_ratio: One of 1:1, 4:3, 3:4, 16:9, 9:16
    
    Returns:
        URL of the generated image
    """
    if not REPLICATE_TOKEN:
        return "Error: REPLICATE_TOKEN not set in environment variables."

    # 调用 Replicate API
    # "Prefer: wait" 表示等图生成完再返回，最多等60秒
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions",
            headers={
                "Authorization": f"Bearer {REPLICATE_TOKEN}",
                "Content-Type": "application/json",
                "Prefer": "wait",
            },
            json={
                "input": {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "output_format": "webp",
                    "output_quality": 90,
                }
            }
        )

    data = resp.json()

    # 如果直接返回结果（Prefer: wait 生效）
    if data.get("status") == "succeeded":
        output = data.get("output")
        # output 可能是列表或字符串
        url = output[0] if isinstance(output, list) else output
        return f"✓ 图片生成成功：{url}"

    # 如果出错
    error = data.get("error") or data.get("detail") or "Unknown error"
    return f"✗ 生成失败：{error}"


# ── 4. 定义工具：查询服务状态 ────────────────────────────────
@mcp.tool()
async def get_status() -> str:
    """Check if leo-imagine service is running and token is configured."""
    token_ok = "✓ 已配置" if REPLICATE_TOKEN else "✗ 未配置"
    return f"leo-imagine 运行中\nReplicate Token: {token_ok}"


# ── 5. 挂载到 FastAPI ────────────────────────────────────────
# MCP 协议通过 SSE（Server-Sent Events）传输
# /mcp 是 Claude 连接的端点
app = FastAPI(title="leo-imagine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 把 MCP 的 Streamable HTTP 路由挂到 /mcp 路径下
# 注意：Anthropic 已从 SSE 迁移到 Streamable HTTP
app.mount("/mcp", mcp.streamable_http_app())

@app.get("/")
async def root():
    return {"service": "leo-imagine", "status": "running"}
