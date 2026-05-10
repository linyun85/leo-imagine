import os
import httpx
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse
from starlette.requests import Request

REPLICATE_TOKEN = os.environ.get("REPLICATE_TOKEN", "")

mcp = FastMCP(
    "leo-imagine",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        allowed_hosts=["leo-imagine.onrender.com", "localhost:*", "127.0.0.1:*"],
        allowed_origins=["https://claude.ai", "https://leo-imagine.onrender.com"],
    )
)


async def poll_prediction(client: httpx.AsyncClient, prediction_id: str) -> dict:
    """轮询直到生成完成"""
    for _ in range(60):
        await asyncio.sleep(2)
        resp = await client.get(
            f"https://api.replicate.com/v1/predictions/{prediction_id}",
            headers={"Authorization": f"Bearer {REPLICATE_TOKEN}"}
        )
        data = resp.json()
        if data.get("status") in ("succeeded", "failed", "canceled"):
            return data
    return {"status": "timeout"}


@mcp.tool()
async def generate_image(prompt: str, aspect_ratio: str = "1:1") -> str:
    """
    Generate an image using Flux 1.1 Pro on Replicate (free tier).
    Args:
        prompt: Image description in any language
        aspect_ratio: One of 1:1, 4:3, 3:4, 16:9, 9:16
    Returns:
        URL of the generated image
    """
    import asyncio

    if not REPLICATE_TOKEN:
        return "Error: REPLICATE_TOKEN not configured."

    async with httpx.AsyncClient(timeout=120) as client:
        # flux-1.1-pro 用标准predictions端点
        resp = await client.post(
            "https://api.replicate.com/v1/models/black-forest-labs/flux-1.1-pro/predictions",
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
                    "safety_tolerance": 2,
                }
            }
        )

        data = resp.json()

        # Prefer: wait 成功直接返回
        if data.get("status") == "succeeded":
            output = data.get("output")
            url = output[0] if isinstance(output, list) else output
            return f"✓ 生成成功：{url}"

        # 如果返回了id但还在处理，轮询
        if data.get("id") and data.get("status") not in ("failed", "canceled"):
            data = await poll_prediction(client, data["id"])
            if data.get("status") == "succeeded":
                output = data.get("output")
                url = output[0] if isinstance(output, list) else output
                return f"✓ 生成成功：{url}"

        error = data.get("error") or data.get("detail") or f"状态: {data.get('status')}"
        return f"✗ 生成失败：{error}"


@mcp.tool()
async def get_status() -> str:
    """Check if leo-imagine service is running and Replicate token is configured."""
    token_ok = "✓ 已配置" if REPLICATE_TOKEN else "✗ 未配置"
    return f"leo-imagine 运行中\nReplicate Token: {token_ok}"


@asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield


async def homepage(request: Request):
    return JSONResponse({"service": "leo-imagine", "status": "running"})


app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/", homepage),
        Mount("/", app=mcp.streamable_http_app()),
    ],
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["Mcp-Session-Id"],
        )
    ],
)
