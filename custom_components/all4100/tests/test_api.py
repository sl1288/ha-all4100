"""Tests for the ALLNET ALL4100 API client and its parser.

Run with:
    uv run --no-sync pytest custom_components/all4100/tests
"""

from http import HTTPStatus
from typing import Any, Self
import xml.etree.ElementTree as ET

from custom_components.all4100.api import (
    All4100AuthError,
    All4100Client,
    All4100ConnectionError,
    All4100ResponseError,
)
import pytest

# Verbatim response captured from the real device (743 bytes).
DEVICE_BODY = (
    '<HTML><HEAD><meta http-equiv="content-type" content="text/html; '
    'charset=ISO-8859-1"></HEAD><BODY><FORM><TEXTAREA COLS=132 ROWS=50>'
    "<xml><data>\n"
    "<devicename>ALL4100</devicename>\n"
    "<rn0>S 1</rn0><rt0>0</rt0>\n"
    "<rn1>S 2</rn1><rt1>0</rt1>\n"
    "<rn2>S 3</rn2><rt2>0</rt2>\n"
    "<rn3>S 4</rn3><rt3>0</rt3>\n"
    "<rn4>S 5</rn4><rt4>1</rt4>\n"
    "<rn5>S 6</rn5><rt5>0</rt5>\n"
    "<rn6>S 7</rn6><rt6>0</rt6>\n"
    "<rn7>S 8</rn7><rt7>0</rt7>\n"
    "<it0>255</it0><it1>255</it1><it2>255</it2><it3>255</it3><it4>239</it4>"
    "<it5>239</it5><it6>255</it6><it7>255</it7>\n"
    "<date>13.08.2013</date><time>00:10:31</time><ad>1</ad><ntpsync>-1</ntpsync>"
    "<sys>362065239</sys><mem>17056</mem><fw>1.06</fw><dev>ALL4100</dev>\n"
    "</data></xml>\n</TEXTAREA></FORM></BODY></HTML>"
)


class FakeResponse:
    """Minimal stand-in for an aiohttp response."""

    def __init__(self, status: int, body: bytes) -> None:
        """Initialize the fake response."""
        self.status = status
        self._body = body

    async def __aenter__(self) -> Self:
        """Enter the context manager."""
        return self

    async def __aexit__(self, *args: object) -> bool:
        """Exit the context manager."""
        return False

    async def read(self) -> bytes:
        """Return the raw body."""
        return self._body


class FakeSession:
    """Minimal stand-in for an aiohttp ClientSession."""

    def __init__(self, response: FakeResponse | Exception) -> None:
        """Initialize the fake session."""
        self._response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        """Record the call and return the canned response."""
        self.calls.append((url, kwargs))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def make_client(
    response: FakeResponse | Exception,
) -> tuple[All4100Client, FakeSession]:
    """Build a client wired to a fake session."""
    session = FakeSession(response)
    client = All4100Client(
        host="10.10.10.10",
        username="admin",
        password="admin",
        session=session,
    )
    return client, session


async def test_parses_real_device_body() -> None:
    """The captured device response yields all 8 relays and device metadata."""
    client, _ = make_client(FakeResponse(200, DEVICE_BODY.encode("iso-8859-1")))

    data = await client.async_get_data()

    assert data.device_name == "ALL4100"
    assert data.model == "ALL4100"
    assert data.firmware == "1.06"
    assert len(data.relays) == 8
    assert [relay.name for relay in data.relays.values()] == [
        "S 1",
        "S 2",
        "S 3",
        "S 4",
        "S 5",
        "S 6",
        "S 7",
        "S 8",
    ]
    # Only relay 4 ("S 4") was on when the response was captured.
    assert data.relays[4].is_on is True
    assert [i for i, relay in data.relays.items() if relay.is_on] == [4]


@pytest.mark.parametrize(
    "relay_name",
    ["R&D", "a<b", "Fileserver & Backup"],
    ids=["ampersand", "less-than", "ampersand-in-words"],
)
async def test_parses_unescaped_relay_names(relay_name: str) -> None:
    """Relay names with XML metacharacters parse, where an XML parser would not.

    The device does not escape names entered in its own web interface, which is
    the reason the parser is regex based rather than XML based.
    """
    body = DEVICE_BODY.replace("S 8", relay_name)
    client, _ = make_client(FakeResponse(200, body.encode("iso-8859-1")))

    data = await client.async_get_data()

    assert data.relays[7].name == relay_name

    # Guard the premise: a real XML parser chokes on exactly this input.
    fragment = body[body.index("<xml>") : body.index("</xml>") + len("</xml>")]
    with pytest.raises(ET.ParseError):
        ET.fromstring(fragment)  # noqa: S314  # asserting that it fails is the point


async def test_decodes_iso_8859_1_names() -> None:
    """Umlauts in relay names survive, despite the missing Content-Type header."""
    body = DEVICE_BODY.replace("S 8", "Küche")
    client, _ = make_client(FakeResponse(200, body.encode("iso-8859-1")))

    data = await client.async_get_data()

    assert data.relays[7].name == "Küche"


async def test_missing_relay_name_falls_back() -> None:
    """A relay reporting a state but no name gets a generated name."""
    body = DEVICE_BODY.replace("<rn4>S 5</rn4>", "")
    client, _ = make_client(FakeResponse(200, body.encode("iso-8859-1")))

    data = await client.async_get_data()

    assert data.relays[4].name == "Relay 5"
    assert data.relays[4].is_on is True


@pytest.mark.parametrize(
    "body",
    ["", "<html><body>Not an ALL4100</body></html>"],
    ids=["empty", "wrong-device"],
)
async def test_unparsable_body_raises(body: str) -> None:
    """A response without relay data is rejected."""
    client, _ = make_client(FakeResponse(200, body.encode("iso-8859-1")))

    with pytest.raises(All4100ResponseError):
        await client.async_get_data()


async def test_unauthorized_raises_auth_error() -> None:
    """HTTP 401 maps to the auth error, so reauth can trigger."""
    client, _ = make_client(FakeResponse(HTTPStatus.UNAUTHORIZED, b"Unauthorized"))

    with pytest.raises(All4100AuthError):
        await client.async_get_data()


async def test_server_error_raises_connection_error() -> None:
    """A non-401 HTTP error maps to the connection error."""
    client, _ = make_client(
        FakeResponse(HTTPStatus.INTERNAL_SERVER_ERROR, b"Server Error")
    )

    with pytest.raises(All4100ConnectionError):
        await client.async_get_data()


async def test_timeout_raises_connection_error() -> None:
    """A timeout maps to the connection error."""
    client, _ = make_client(TimeoutError())

    with pytest.raises(All4100ConnectionError):
        await client.async_get_data()


@pytest.mark.parametrize(
    ("is_on", "expected_v"),
    [(True, "1"), (False, "0")],
    ids=["turn-on", "turn-off"],
)
async def test_set_relay_builds_expected_request(is_on: bool, expected_v: str) -> None:
    """Switching a relay hits /relais with the documented query parameters."""
    client, session = make_client(FakeResponse(200, b"<HTML></HTML>"))

    await client.async_set_relay(7, is_on)

    url, kwargs = session.calls[0]
    assert url == "http://10.10.10.10/relais"
    assert kwargs["params"] == {"r": "7", "v": expected_v, "tm": "0"}


async def test_sends_basic_auth_header() -> None:
    """Credentials are sent as an Authorization header."""
    client, session = make_client(FakeResponse(200, DEVICE_BODY.encode("iso-8859-1")))

    await client.async_get_data()

    _, kwargs = session.calls[0]
    # "admin:admin" base64 encoded.
    assert kwargs["headers"]["Authorization"] == "Basic YWRtaW46YWRtaW4="
