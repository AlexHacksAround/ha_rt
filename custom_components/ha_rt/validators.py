"""Input validators for the Service Management integration."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from .exceptions import RTError


class InvalidURL(RTError):
    """Error to indicate an invalid or unsafe URL."""


# Private/internal IP ranges that should be blocked
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),        # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),     # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),    # Private Class C
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 private
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]

# Hostnames that should be blocked
BLOCKED_HOSTNAMES = [
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",      # GCP metadata
    "metadata.internal",             # Generic cloud metadata
]

# Patterns for cloud metadata endpoints
BLOCKED_HOSTNAME_PATTERNS = [
    re.compile(r"^169\.254\.169\.254$"),       # AWS/Azure/GCP metadata IP
    re.compile(r".*\.internal$"),               # Internal domains
    re.compile(r".*\.local$"),                  # mDNS domains
]


def validate_rt_url(url: str, allow_http: bool = False) -> str:
    """Validate RT server URL for security.

    Args:
        url: The URL to validate
        allow_http: If True, allow http:// (for testing only)

    Returns:
        The validated URL

    Raises:
        InvalidURL: If the URL is invalid or points to a blocked destination
    """
    if not url:
        raise InvalidURL("URL cannot be empty")

    # Parse the URL
    try:
        parsed = urlparse(url)
    except Exception as err:
        raise InvalidURL(f"Invalid URL format: {err}") from err

    # Check scheme
    if not allow_http and parsed.scheme != "https":
        raise InvalidURL("Only HTTPS URLs are allowed for security")
    if parsed.scheme not in ("http", "https"):
        raise InvalidURL(f"Invalid URL scheme: {parsed.scheme}")

    # Check hostname exists
    hostname = parsed.hostname
    if not hostname:
        raise InvalidURL("URL must include a hostname")

    # Check against blocked hostnames
    hostname_lower = hostname.lower()
    if hostname_lower in BLOCKED_HOSTNAMES:
        raise InvalidURL(f"Blocked hostname: {hostname}")

    # Check against blocked hostname patterns
    for pattern in BLOCKED_HOSTNAME_PATTERNS:
        if pattern.match(hostname_lower):
            raise InvalidURL(f"Blocked hostname pattern: {hostname}")

    # Try to parse as IP address and check against blocked networks
    try:
        ip = ipaddress.ip_address(hostname)
        for network in BLOCKED_IP_NETWORKS:
            if ip in network:
                raise InvalidURL(f"Blocked IP range: {hostname}")
    except ValueError:
        # Not an IP address, it's a hostname - that's fine
        pass

    # Ensure path doesn't try to access unexpected endpoints
    # RT REST2 API should be at /REST/2.0/
    # We just store the base URL, so no path validation needed here

    return url
