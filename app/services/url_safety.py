
import ipaddress
import socket
from urllib.parse import urlsplit


def validate_public_url(url: str) -> None:
    """Allow only public HTTP/HTTPS URLs on standard ports."""
    try:
        parsed = urlsplit(url)

        if parsed.scheme.lower() not in {"http", "https"}:
            raise ValueError("Only HTTP and HTTPS URLs are allowed.")

        if not parsed.hostname:
            raise ValueError("URL must contain a hostname.")

        if parsed.username or parsed.password:
            raise ValueError("URLs containing credentials are not allowed.")

        port = parsed.port
        allowed_ports = {80, 443}

        if port is not None and port not in allowed_ports:
            raise ValueError("Only ports 80 and 443 are allowed.")

        hostname = parsed.hostname.rstrip(".").lower()

        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ValueError("Localhost URLs are not allowed.")

        try:
            addresses = [ipaddress.ip_address(hostname)]
        except ValueError:
            try:
                records = socket.getaddrinfo(
                    hostname,
                    port or (443 if parsed.scheme.lower() == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            except socket.gaierror as exc:
                raise ValueError("Hostname could not be resolved.") from exc

            addresses = [
                ipaddress.ip_address(record[4][0])
                for record in records
            ]

        if not addresses:
            raise ValueError("Hostname did not resolve to an IP address.")

        if any(not address.is_global for address in addresses):
            raise ValueError(
                "URLs resolving to private or non-public IP addresses are not allowed."
            )

    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Invalid URL.") from exc
