# Postman collection

`garden-of-eden.postman_collection.json` describes the REST API served by this fork
(branch `gardyn-home3`), with example responses captured from a Gardyn Home 3.0.

- **v1**: the API the device serves today. Requests marked ⚠ drive real hardware
  (pump, lights).
- **v2**: the planned changes, which return 404 until implemented. See the
  schedule/presets/plants proposal in the `code.gardyn` repo.

## Use

1. Import both JSON files into Postman.
2. Select the `gardyn.lan` environment and set `apiKey` (a secret variable; the key is in the
   password manager, never in this repo). `baseUrl` defaults to `http://gardyn.lan:5000`.
3. `/`, `/health` and requests from the Pi itself need no key.

## Regenerate

`build_collection.py <responses-dir> docs/postman` rebuilds both files. `<responses-dir>`
holds one `<path>.json` (body) and `<path>.json.status` (HTTP code) per GET endpoint, for
example `light_brightness.json`, captured from a device.
