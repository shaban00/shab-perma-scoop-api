"""
`utils.check_proxy_port` module: Checks whether a proxy port is available.
"""

import requests


def check_proxy_port(proxy_port: int) -> bool:
    """Check whether the specified proxy port is available."""
    proxy_port_is_available = False
    try:
        requests.head(f"http://localhost:{proxy_port}", timeout=1)
    except requests.exceptions.ReadTimeout:
        return False
    except Exception:
        proxy_port_is_available = True
    return proxy_port_is_available
