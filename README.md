# ALLNET ALL4100 for Home Assistant

Home Assistant integration for the **ALLNET ALL4100 Ethernet Power Switch**, a
19" rack unit with eight individually switchable IEC outlets.

Each relay is exposed as a switch entity, named from the label configured in the
device's own web interface. All eight relays are fully controllable.

## Features

- Config flow — set up entirely from the Home Assistant UI, no YAML
- Eight switch entities with device class `outlet`
- Relay names are read from the device and follow renames made in its web UI
- Device page shows model, firmware version and a link to the web interface
- Re-authentication when the device password changes
- Reconfiguration when the device changes IP address
- Local polling every 15 seconds, no cloud dependency

## Requirements

- An ALL4100 reachable over HTTP on the local network
- The user name and password of its web interface

## Installation

### HACS (custom repository)

1. HACS → Integrations → ⋮ → **Custom repositories**
2. Add this repository to HACS as a custom repository with category **Integration**
3. Install **ALLNET ALL4100**, then restart Home Assistant

### Manual

Copy `custom_components/all4100` into your Home Assistant `config/custom_components`
directory and restart Home Assistant.

## Configuration

Settings → Devices & Services → **Add Integration** → search for
**ALLNET ALL4100**, then enter the host, user name and password.

The integration creates one device with eight switch entities, for example
`switch.all4100_konsole`.

## Removal

Settings → Devices & Services → ALLNET ALL4100 → ⋮ → **Delete**. Nothing is
written to the device, so no cleanup is needed there.

## How it works

The ALL4100 firmware (1.06) predates modern APIs. The integration uses the two
HTTP endpoints the device offers, both behind HTTP basic auth:

| Endpoint | Purpose |
| --- | --- |
| `GET /xml` | Device name, model, firmware and all eight relay names and states |
| `GET /relais?r=<0-7>&v=<0\|1>&tm=0` | Switch one relay on (`v=1`) or off (`v=0`) |

Two quirks of that firmware are handled in [`api.py`](custom_components/all4100/api.py):

- **No `Content-Type` header.** The response is ISO-8859-1, so the raw bytes are
  decoded explicitly. Umlauts in relay names survive.
- **Unescaped user input.** The `/xml` payload embeds relay names verbatim, so a
  name containing `&` or `<` produces malformed XML. Parsing is therefore
  regex based rather than XML based; the payload is a flat, fixed set of leaf
  tags, so this is both sufficient and more robust. See
  `test_parses_unescaped_relay_names` for the regression test.

## Known limitations

- The device exposes no MAC address or serial number, so it cannot be
  identified across a delete/re-add cycle. Duplicate entries are prevented by
  host address instead.
- No discovery — the device supports neither mDNS nor SSDP.
- The `/xml` payload also carries uptime, free memory and NTP status. These are
  not exposed as entities.

## Development

```bash
pytest ha-all4100
```

The tests cover the parser and the HTTP error mapping against a captured device
response, without touching real hardware.
