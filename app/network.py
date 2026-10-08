"""LAN IP discovery and QR code generation."""
from __future__ import annotations

import io
import socket

import qrcode
import qrcode.constants


def get_lan_ip() -> str:
    """Best-effort LAN IP of this machine.

    Opens a UDP socket toward a public address without sending any packets
    (UDP connect() just picks the outbound route/interface) so it works
    offline and without a default route to the internet in most cases; if
    that fails outright, falls back to the hostname resolution, then
    loopback.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass

    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass

    return "127.0.0.1"


def make_qr_ascii(data: str) -> str:
    """Render a QR code as ASCII art suitable for printing to a terminal."""
    qr = qrcode.QRCode(border=1)
    qr.add_data(data)
    qr.make(fit=True)
    buf = io.StringIO()
    qr.print_ascii(out=buf, tty=False)
    return buf.getvalue()


def make_qr_png_base64(data: str) -> str:
    """Render a QR code as a base64 PNG data URI for embedding in HTML."""
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    import base64

    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
