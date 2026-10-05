"""
VeriSlip API Main Application.
"""

import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.middleware.request_tracing import RequestTracingMiddleware
from api.middleware.rate_limiter import ApiKeyRateLimitMiddleware
from api.middleware.prometheus_metrics import PrometheusMetricsMiddleware
from api.middleware.upload_security import UploadBodyLimitMiddleware
from api.routes.verify import router as verify_router
from api.routes.live_scanner import router as live_scanner_router
from api.routes.webhook_whatsapp import router as whatsapp_router
from api.routes.reports import router as reports_router
from api.routes.integrations import router as integrations_router
from api.routes.analytics import router as analytics_router
from api.routes.courier import router as courier_router
from api.routes.shopify import router as shopify_router
from api.routes.triage_feedback import router as triage_router
from api.routes.active_learning import router as active_learning_router
from api.routes.clearing import router as clearing_router
from api.routes.threat_intel import router as threat_intel_router
from api.routes.crypto import router as crypto_router
from core.observability.logging import configure_json_logging
from core.observability.metrics import get_metrics_payload, CONTENT_TYPE_LATEST
from starlette.responses import Response

configure_json_logging()

app = FastAPI(
    title="VeriSlip Forensic API",
    description="AI-powered forensic tamper detection for bank transfer slips and payment receipts in P2P commerce.",
    version="1.0.0"
)

app.add_middleware(ApiKeyRateLimitMiddleware)
app.add_middleware(PrometheusMetricsMiddleware)

# Enable CORS for cross-origin web apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Request-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After",
    ],
)

# Enforce upload body limits before multipart/JSON parsers can spool or allocate
# attacker-controlled request bodies. Route-level per-file checks remain active.
app.add_middleware(UploadBodyLimitMiddleware)

# Added last so tracing also wraps rate-limit and CORS short-circuit responses.
app.add_middleware(RequestTracingMiddleware)

# Include API Routers
app.include_router(verify_router)
app.include_router(live_scanner_router)
app.include_router(whatsapp_router)
app.include_router(reports_router)
app.include_router(integrations_router)
app.include_router(analytics_router)
app.include_router(courier_router, prefix="/api/v1")
app.include_router(shopify_router)
app.include_router(triage_router)
app.include_router(active_learning_router)
app.include_router(clearing_router)
app.include_router(threat_intel_router)
app.include_router(crypto_router)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "VeriSlip Forensic Engine",
        "version": "1.0.0",
        "supported_banks": ["COMBANK", "SAMPATH", "BOC", "HNB", "PEOPLES", "DFCC", "PAN_ASIA", "SEYLAN", "NTB_FRIMI", "GENERIC_CEFTS"]
    }

@app.get("/metrics")
def metrics():
    """Prometheus exposition endpoint for latency, throughput, and forensic layer telemetry."""
    return Response(content=get_metrics_payload(), media_type=CONTENT_TYPE_LATEST)

# Mount static web directory
web_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))
if os.path.exists(web_dir):
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

    @app.get("/")
    def serve_cockpit():
        index_file = os.path.join(web_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "VeriSlip API is running. Web UI not found."}
