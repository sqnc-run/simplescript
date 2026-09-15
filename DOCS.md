# sqnc.run — technical documentation

## stream

sqnc.run broadcasts a continuous public binary stream — 49-bit frames at 200ms intervals.
anyone can listen. anyone can transmit.

---

## websocket — listen to the stream

**endpoint:** `wss://sqnc.run/ws`  
**protocol:** WebSocket over TLS  
**message format:** string of exactly 49 characters, each `0` or `1`  
**frequency:** ~5 messages per second (200ms interval)  

### example (Python)

```python
import websocket
import ssl
import certifi

def on_message(ws, message):
    print(message)  # 49-character binary string

ws = websocket.WebSocketApp("wss://sqnc.run/ws", on_message=on_message)
ctx = ssl.create_default_context(cafile=certifi.where())
ws.run_forever(sslopt={"context": ctx})
```

### example (JavaScript)

```javascript
const ws = new WebSocket("wss://sqnc.run/ws");
ws.onmessage = (event) => {
    console.log(event.data); // 49-character binary string
};
```

---

## http post — inject a sequence

**endpoint:** `https://sqnc.run/inject`  
**method:** POST  
**content-type:** `application/json`  

### body

```json
{
  "sequence": "0101010101010101010101010101010101010101010101010"
}
```

the `sequence` field must be:
- a string of `0` and `1` only
- a multiple of 49 characters (one frame = 49 bits)
- maximum 15 frames (735 characters)

### success response

```json
HTTP 200
{
  "ok": true,
  "frames": 1
}
```

### error responses

| status | reason | detail |
|--------|--------|--------|
| 400 | length not a multiple of 49 | `"invalid length N: must be a multiple of 49"` |
| 400 | characters other than 0 and 1 | `"invalid characters: only 0 and 1 allowed"` |
| 400 | too many frames | `"max N frames"` |
| 429 | inject too soon | `"wait N seconds before next inject"` |

### rate limiting

there is a per-IP cooldown between consecutive injects (currently 20 seconds).  
if you inject before the cooldown expires, the API returns `429` with the remaining wait time in seconds.

### CORS

the inject endpoint only accepts requests from `https://sqnc.run`.  
calls from other origins (other domains, localhost) will be blocked by CORS.  
if you need to inject from your own application, use a server-side request — not a browser fetch.

### example (curl)

```bash
curl -X POST https://sqnc.run/inject \
     -H "Content-Type: application/json" \
     -d '{"sequence": "0000000000000000000000000000000000000000000000000"}'
```

### example (Python)

```python
import requests

sequence = "0" * 49  # one black frame
response = requests.post("https://sqnc.run/inject", json={"sequence": sequence})
print(response.json())  # {"ok": true, "frames": 1}
```

---

## frame format

a frame is a 7x7 binary grid, serialized as a string of 49 characters read left to right, top to bottom.

```
0 0 0 0 0 0 0
0 0 1 1 0 0 0
0 0 1 1 0 0 0
0 0 0 0 0 0 0
0 0 0 0 0 0 0
0 0 0 0 0 0 0
0 0 0 0 0 0 0
```

serialized: `0000000001100000110000000000000000000000000000000`

`0` = off (black) — `1` = on (white)

---

transmit@sqnc.run
