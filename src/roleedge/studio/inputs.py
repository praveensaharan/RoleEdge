"""Turning a shared link into text the reader can use. The page is data, never instructions (T2).

The server fetches the page, so the fetch is guarded against server-side request forgery and against slow or
hostile pages:

* only http(s) on the default ports, no credentials in the URL;
* every address the host resolves to must be public (no loopback, private, link-local such as the cloud metadata
  address 169.254.169.254, or reserved ranges), and the connection goes to the address that was checked, so a host
  that answers differently the second time (DNS rebinding) can't steer it inside;
* every redirect hop is checked again, the body is capped in size, and the whole fetch has one deadline;
* the page is read with the standard HTML parser, which stays linear on hostile markup (regexes over a whole page
  don't, and they hold the interpreter lock while they run).
"""

from __future__ import annotations

import ipaddress
import socket
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

MAX_CHARS = 12_000
MAX_BYTES = 1_000_000
MAX_REDIRECTS = 3
DEADLINE_S = 20.0
TEXT_TYPES = ("text/html", "text/plain", "application/xhtml+xml")
NAT64 = ipaddress.ip_network("64:ff9b::/96")  # "global", but a NAT64 gateway would turn it into the embedded IPv4 address


def _public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not (ip.version == 6 and ip in NAT64)


def public_address(url: str) -> str | None:
    """The address to connect to if ``url`` is http(s) on a default port and every address its host resolves to is
    public; otherwise None."""
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        return None
    if port not in (None, 80, 443):
        return None
    try:
        infos = socket.getaddrinfo(parts.hostname, port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        return None
    addresses = sorted({info[4][0].split("%")[0] for info in infos})
    if not addresses or not all(_public(a) for a in addresses):
        return None
    return addresses[0]


def is_public_url(url: str) -> bool:
    return public_address(url) is not None


def _guarded_get(url: str, types: tuple[str, ...], max_bytes: int, deadline_s: float) -> tuple[bytes, str, str] | None:
    """(body, content type, final URL) of a public URL whose content type starts with one of ``types``, with every
    redirect hop checked again, the body capped and one deadline; None if it can't be fetched safely."""
    url = url.strip()
    deadline = time.monotonic() + deadline_s
    try:
        with httpx.Client(follow_redirects=False, headers={"User-Agent": "roleEdge/0.1"}) as client:
            for _ in range(MAX_REDIRECTS + 1):
                address = public_address(url)
                left = deadline - time.monotonic()
                if address is None or left <= 0:
                    return None
                response = client.send(_pinned_request(client, url, address, left), stream=True)
                try:
                    if response.is_redirect and response.headers.get("location"):
                        url = urljoin(url, response.headers["location"])
                        continue
                    kind = response.headers.get("content-type", "")
                    if response.status_code != 200 or not kind.startswith(types):
                        return None
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body += chunk
                        if len(body) >= max_bytes or time.monotonic() > deadline:
                            break
                    if len(body) >= max_bytes and not kind.startswith(TEXT_TYPES):
                        return None  # a picture cut short is no picture
                    return bytes(body[:max_bytes]), kind, url
                finally:
                    response.close()
    except httpx.HTTPError:
        return None
    return None


def link_text(url: str, deadline_s: float = DEADLINE_S) -> str:
    """The readable text of a public web page (title + body text, scripts and styles removed), or "" if it can't be
    read safely within ``deadline_s`` seconds."""
    got = _guarded_get(url, TEXT_TYPES, MAX_BYTES, deadline_s)
    if got is None:
        return ""
    body, kind, _ = got
    charset = kind.split("charset=")[-1].split(";")[0].strip() if "charset=" in kind else "utf-8"
    return page_text(body.decode(charset or "utf-8", errors="replace"))


IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")
MAX_IMAGE_BYTES = 3_000_000


class _Meta(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.image = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "meta" and not self.image:
            a = {k: v for k, v in attrs if v}
            if a.get("property") in ("og:image", "og:image:url", "og:image:secure_url") or a.get("name") in ("twitter:image", "og:image"):
                self.image = a.get("content", "")


def page_image(url: str, deadline_s: float = DEADLINE_S) -> tuple[bytes, str] | None:
    """The picture a public page offers for itself (its og:image, as a shop shows a product), fetched with the same
    guards: (image bytes, file extension), or None."""
    got = _guarded_get(url, TEXT_TYPES, MAX_BYTES, deadline_s)
    if got is None:
        return None
    body, _, final = got
    parser = _Meta()
    parser.feed(body.decode("utf-8", errors="replace"))
    if not parser.image:
        return None
    image = _guarded_get(urljoin(final, parser.image), IMAGE_TYPES, MAX_IMAGE_BYTES, deadline_s)
    if image is None:
        return None
    data, kind, _ = image
    return data, {"image/png": "png", "image/webp": "webp"}.get(kind.split(";")[0], "jpg")


def _pinned_request(client: httpx.Client, url: str, address: str, timeout: float) -> httpx.Request:
    """A GET for ``url`` that connects to ``address`` (already checked), while TLS and the Host header still use the
    real name, so certificates are verified as usual."""
    parts = urlsplit(url)
    host = f"[{address}]" if ":" in address else address
    target = urlunsplit(parts._replace(netloc=host + (f":{parts.port}" if parts.port else "")))
    return client.build_request("GET", target, headers={"Host": parts.hostname}, timeout=timeout,
                                extensions={"sni_hostname": parts.hostname})


class _Text(HTMLParser):
    SKIP = frozenset({"script", "style", "noscript", "template", "svg"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: list[str] = []
        self.text: list[str] = []
        self.skipping = 0
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self.SKIP:
            self.skipping += 1
        elif tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title.append(data)
        elif not self.skipping:
            self.text.append(data)


def page_text(page: str) -> str:
    """Title and visible text of an HTML (or plain text) page, whitespace collapsed, cut to MAX_CHARS."""
    parser = _Text()
    parser.feed(page)
    parser.close()
    title = " ".join("".join(parser.title).split())
    text = " ".join(" ".join(parser.text).split())
    return (f"{title}\n\n" if title else "") + text[:MAX_CHARS]
