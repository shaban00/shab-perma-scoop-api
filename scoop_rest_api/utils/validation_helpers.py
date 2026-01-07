"""
`utils.validation_helpers` module: Utilities for confirming a given URL can be captured.
"""

from flask import current_app
from netaddr import IPAddress, IPNetwork
import requests
import socket
import ssl
from urllib.parse import urlparse
from urllib3 import poolmanager
from contextlib import contextmanager
import threading

# Don't warn us about making insecure requests: we plan to capture even insecure sites,
# so don't worry about that when validating
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class Sec1TLSAdapter(requests.adapters.HTTPAdapter):
    """
    Debian + OpenSSL evidently set a minimum TLS version of 1.2,
    and there's a problem that results in SSL: DH_KEY_TOO_SMALL errors, for some websites.
    Lower the security standard for our requests, per https://github.com/psf/requests/issues/4775
    """

    def init_poolmanager(self, connections, maxsize, block=False):
        """Create and initialize the urllib3 PoolManager."""
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")

        # for whatever reason, required for verify=False
        ctx.check_hostname = False
        self.poolmanager = poolmanager.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_version=ssl.PROTOCOL_TLS,
            ssl_context=ctx,
        )

    def cert_verify(self, conn, url, verify, cert):
        super().cert_verify(conn, url, False, cert)


def resolve_ip(url):
    """
    Return None if the domain name does not resolve to an IP address,
    or raise OSError if the lookup times out.
    """
    parsed = urlparse(url)
    try:
        return socket.gethostbyname(parsed.netloc.split(":")[0])
    except socket.gaierror:
        return None


def validate_ip(ip):
    """Return False if the IP is blocked."""
    if not ip:
        return False
    ip = IPAddress(ip)
    for banned_ip_range in current_app.config["BANNED_IP_RANGES"]:
        if IPAddress(ip) in IPNetwork(banned_ip_range):
            return False
    return True


class GetHeadersThread(threading.Thread):
    """
    Run python request.get() in a thread.
    Once the thread is done, see `self.response` and `self.exception` for the results.
    """

    def __init__(self, url, user_agent, headers, read_timeout, *args, **kwargs):
        from flask import current_app  # noqa

        self.logger = current_app.logger
        self.user_agent = user_agent
        self.headers = headers
        self.read_timeout = read_timeout
        self.url = url
        self.response = None
        self.exception = None

        super().__init__(*args, **kwargs)

    def run(self):

        try:
            with requests.Session() as s:
                # Break noisily if requests mediates anything but http and https
                assert list(s.adapters.keys()) == ["https://", "http://"]

                # Lower our standards for the required TLS security level
                s.mount("https://", Sec1TLSAdapter())

                response = s.get(
                    self.url,
                    headers={
                        "User-Agent": self.user_agent,
                        **self.headers,
                    },
                    timeout=max(self.read_timeout, 1),
                    stream=True,  # we're only looking at the headers
                )
                self.response = response
        except (
            requests.ConnectionError,
            requests.Timeout,
        ):
            self.logger.debug(
                f"Communication with URL failed during validation: {self.url}.",
            )
        except (requests.exceptions.InvalidSchema,):
            # InvalidSchema is raised if the retrieved URL uses a protocol not handled by
            # requests' adapters
            # (https://github.com/psf/requests/blob/master/requests/sessions.py#L419)
            # While we can validate the target URL in advance,
            # it may redirect to any arbitrary schema,
            # for instance, file://, which will raise InvalidSchema.
            self.logger.debug(
                f"Invalid schema detected when validating: {self.url}.",
            )
        except (requests.exceptions.InvalidURL,):
            # InvalidURL is raised when requests cannot parse the target of a redirect.
            # (https://github.com/psf/requests/blob/8149e9fe54c36951290f198e90d83c8a0498289c/requests/models.py#L383)
            # We still return None, to indicate in all cases that we did not successfully retrieve
            # any headers, rather than propagating the exception.
            self.logger.debug(
                f"Invalid redirect encountered when validating: {self.url}.",
            )
        except Exception as e:
            # If an unexpected exception occurs, pass that up to the main thread
            self.exception = e
        finally:
            if self.response:
                self.response.close()


def get_response(url):

    user_agent = current_app.config["VALIDATION_USER_AGENT"]

    # check if a custom user agent has been set for this domain
    from scoop_rest_api.utils.get_custom_agents import get_custom_agents  # noqa

    domain = urlparse(url).hostname
    if custom_agents := get_custom_agents(domain):
        custom_validation_ua = custom_agents.get("validator_ua")
        if custom_validation_ua:
            user_agent = custom_validation_ua

    current_app.logger.debug(f"Validating with user agent: {user_agent}")

    headers_thread = GetHeadersThread(
        url,
        user_agent,
        current_app.config["VALIDATION_EXTRA_HEADERS"],
        current_app.config["VALIDATION_TIMEOUT"] - 1,
        daemon=True,
    )
    headers_thread.start()
    headers_thread.join(timeout=current_app.config["VALIDATION_TIMEOUT"])
    if headers_thread.is_alive():
        current_app.logger.info(
            f"Header retrieval timed out for {url}.",
        )
        return None
    if headers_thread.exception:
        current_app.logger.error(
            "Exception while getting headers.", exc_info=headers_thread.exception
        )
        return None
    return headers_thread.response


def get_content_length(headers):
    """Return the value of the content-length header as an int, or None if invalid or absent"""
    lowercased_headers = {k.lower(): headers[k] for k in headers}
    content_length = None
    try:
        content_length = int(lowercased_headers.get("content-length"))
    except (TypeError, ValueError):
        # content-length header wasn't present or wasn't an integer.
        pass
    return content_length
