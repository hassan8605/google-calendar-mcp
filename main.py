import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.mcp_server.server import create_mcp_server
from src import api_router
from src.settings import settings

app = FastAPI(
    title="Calendar MCP",
    description="Google Calendar MCP Server with NLP scheduling via Claude",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ───────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REST API routes ────────────────────────────────────────────
app.include_router(api_router, prefix="/api")

# ── MCP server (SSE transport) ─────────────────────────────────
# Claude Desktop connects to: GET http://localhost:4325/mcp/sse
_mcp = create_mcp_server()
app.mount("/mcp", _mcp.sse_app())


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.ENVIRONMENT == "development",
    )
