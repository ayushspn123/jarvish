"""Generate a self-signed TLS certificate so the web app can serve HTTPS.

Phones block microphone access on plain http:// (non-localhost), so HTTPS is required for voice
on your phone. This makes cert.pem / key.pem covering localhost and your LAN IPs. Your phone will
show a one-time "not secure" warning you can accept (it's your own cert).

Run:  .venv\\Scripts\\python.exe -m webapp.make_cert
"""

from __future__ import annotations

import datetime
import ipaddress
import os
import socket

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

_HERE = os.path.dirname(os.path.abspath(__file__))


def _local_ips() -> list[str]:
    ips = {"127.0.0.1"}
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            addr = info[4][0]
            if ":" not in addr:  # IPv4 only
                ips.add(addr)
    except socket.gaierror:
        pass
    return sorted(ips)


def main() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    sans = [x509.DNSName("localhost")]
    for ip in _local_ips():
        try:
            sans.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except ValueError:
            pass

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "JARVIS")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .sign(key, hashes.SHA256())
    )

    with open(os.path.join(_HERE, "key.pem"), "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
    with open(os.path.join(_HERE, "cert.pem"), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print("Created cert.pem / key.pem covering:", ", ".join(_local_ips()))


if __name__ == "__main__":
    main()
