"""HTML page routes: laptop dashboard and the phone-facing pages."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import RESOURCE_DIR, settings
from app.network import make_qr_png_base64

router = APIRouter()
templates = Jinja2Templates(directory=str(RESOURCE_DIR / "app" / "templates"))


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    url = settings.base_url()
    mobile_url = f"{url}/m"
    qr_target = f"{mobile_url}?t={settings.qr_token}" if settings.require_pin else mobile_url
    qr_data_uri = make_qr_png_base64(qr_target)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "lan_url": url,
            "mobile_url": mobile_url,
            "qr_data_uri": qr_data_uri,
            "pin": settings.pin,
            "require_pin": settings.require_pin,
            "dest_dir": str(settings.dest_dir),
        },
    )


@router.get("/m", response_class=HTMLResponse)
def mobile_home(request: Request):
    return templates.TemplateResponse(request, "mobile.html", {})


@router.get("/sw.js")
def service_worker():
    # Served at the root path (not /static/sw.js) so its scope covers "/" and "/m".
    return FileResponse(RESOURCE_DIR / "app" / "static" / "sw.js", media_type="application/javascript")
