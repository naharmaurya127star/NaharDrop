"""Phase 4: optional self-signed HTTPS.

Generates (and caches) a self-signed certificate covering the laptop's LAN
IP, localhost and 127.0.0.1, using the `cryptography` library. If the user
already has a trusted cert (e.g. from `mkcert`), run.py's --cert-file /
--key-file flags bypass this entirely.
"""
from __future__ import annotations

import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def ensure_self_signed_cert(data_dir: Path, lan_ip: str) -> tuple[Path, Path]:
    cert_path = data_dir / "cert.pem"
    key_path = data_dir / "key.pem"
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    data_dir.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "NaharDrop")])
    alt_names: list[x509.GeneralName] = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    try:
        alt_names.append(x509.IPAddress(ipaddress.ip_address(lan_ip)))
    except ValueError:
        pass

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path
