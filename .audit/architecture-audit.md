# Architecture Audit

Score: **3/5 (Adequate)**

Scope focus: WS lifecycle, reconnection behavior, proxy correctness, error handling.

## Findings

### HIGH - No delivery acknowledgment path for `chat.send`
- **File:Line:** `server.py:576`
- **What is wrong:** Outbound messages are forwarded to gateway, but corresponding `res` frames for those request IDs are never tracked or surfaced to browser. Failures are silent.
- **Suggested fix:** Track pending request IDs, handle success/error `res` frames, and emit explicit browser events (`sent`, `send_error`).

### MEDIUM - Race-prone access to `history_req_id`
- **File:Line:** `server.py:527`
- **What is wrong:** `gateway_ref.get("history_req_id")` is read without lock while reconnect logic mutates it in `finally`, creating potential misassociation during reconnect churn.
- **Suggested fix:** Read both `ws` and `history_req_id` under `gateway_lock`, or use immutable connection-context objects.

### MEDIUM - Backpressure model incomplete across browser->gateway path
- **File:Line:** `server.py:479`, `server.py:560`
- **What is wrong:** There is no bounded backpressure between browser intake and gateway send availability.
- **Suggested fix:** Bound queue, apply drop/reject policy, and report congestion to client.

### LOW - Generic reconnect error hides cause granularity
- **File:Line:** `server.py:548`
- **What is wrong:** All gateway disconnect/error modes collapse to one browser message, reducing operator debuggability.
- **Suggested fix:** Classify known failure modes (DNS, auth reject, handshake timeout, protocol mismatch) into distinct user-safe error codes.

## Positive Notes
- WS lifecycle has clear shutdown handling (`stop_event`, task cancel, close guards): `server.py:621`-`server.py:631`.
- Reconnect backoff is implemented and bounded: `server.py:490`, `server.py:557`-`server.py:558`.
