"""Low-level HTTP client for the ALLNET ALL4100 Ethernet Power Switch.

This module deliberately has no Home Assistant imports so it can be unit tested
on its own.
"""

from dataclasses import dataclass
from http import HTTPStatus
import re
from typing import Final

from aiohttp import ClientError, ClientSession, ClientTimeout, encode_basic_auth

RELAY_COUNT: Final = 8

# The device serves ISO-8859-1 but sends no Content-Type header at all, so the
# encoding has to be applied explicitly to the raw bytes.
ENCODING: Final = "iso-8859-1"

REQUEST_TIMEOUT: Final = ClientTimeout(total=10)


class All4100Error(Exception):
    """Base error for the ALL4100 client."""


class All4100ConnectionError(All4100Error):
    """Raised when the device is unreachable or returns an HTTP error."""


class All4100AuthError(All4100Error):
    """Raised when the device rejects the credentials."""


class All4100ResponseError(All4100Error):
    """Raised when the response is not a recognisable ALL4100 status page."""


@dataclass(frozen=True, kw_only=True, slots=True)
class All4100Relay:
    """State of a single relay."""

    index: int
    name: str
    is_on: bool


@dataclass(frozen=True, kw_only=True, slots=True)
class All4100Data:
    """Device status as returned by the /xml endpoint."""

    device_name: str
    model: str
    firmware: str | None
    relays: dict[int, All4100Relay]


def _tag(body: str, tag: str) -> str | None:
    """Return the text of a single flat leaf tag, or None if absent.

    Regex rather than an XML parser: relay names are free text entered in the
    device's own web interface and are not entity-escaped, so a name containing
    "&" or "<" makes any real XML parser raise. The payload is a flat, fixed set
    of leaf tags, so a non-greedy match is both sufficient and more robust.
    """
    if match := re.search(rf"<{tag}>(.*?)</{tag}>", body, re.DOTALL):
        return match.group(1).strip()
    return None


class All4100Client:
    """Talk to an ALL4100 over its HTTP interface."""

    def __init__(
        self,
        *,
        host: str,
        username: str,
        password: str,
        session: ClientSession,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._base_url = f"http://{host.strip().rstrip('/')}"
        # aiohttp.BasicAuth and the auth= kwarg are deprecated since aiohttp 3.14
        # in favour of an explicit Authorization header.
        self._headers = {"Authorization": encode_basic_auth(username, password)}

    async def _async_request(
        self, path: str, params: dict[str, str] | None = None
    ) -> str:
        """Perform a GET request and return the decoded body."""
        try:
            async with self._session.get(
                f"{self._base_url}{path}",
                params=params,
                headers=self._headers,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                status = response.status
                raw = await response.read()
        except (ClientError, TimeoutError) as err:
            raise All4100ConnectionError(
                f"Error communicating with {self._base_url}: {err}"
            ) from err

        # Distinguished from other HTTP errors so that reauth can trigger.
        if status == HTTPStatus.UNAUTHORIZED:
            raise All4100AuthError(
                f"Device at {self._base_url} rejected the credentials"
            )
        if status >= HTTPStatus.BAD_REQUEST:
            raise All4100ConnectionError(
                f"Device at {self._base_url} returned HTTP {status}"
            )

        return raw.decode(ENCODING, errors="replace")

    async def async_get_data(self) -> All4100Data:
        """Fetch and parse the device status."""
        body = await self._async_request("/xml")

        relays: dict[int, All4100Relay] = {}
        for index in range(RELAY_COUNT):
            if (state := _tag(body, f"rt{index}")) is None:
                continue
            relays[index] = All4100Relay(
                index=index,
                name=_tag(body, f"rn{index}") or f"Relay {index + 1}",
                is_on=state == "1",
            )

        if not relays:
            raise All4100ResponseError(
                f"No relay data found in response from {self._base_url}/xml"
            )

        return All4100Data(
            device_name=_tag(body, "devicename") or "ALL4100",
            model=_tag(body, "dev") or "ALL4100",
            firmware=_tag(body, "fw"),
            relays=relays,
        )

    async def async_set_relay(self, index: int, is_on: bool) -> None:
        """Switch a relay on or off."""
        await self._async_request(
            "/relais",
            params={"r": str(index), "v": "1" if is_on else "0", "tm": "0"},
        )
