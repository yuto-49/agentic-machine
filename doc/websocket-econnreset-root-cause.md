# Why `ws proxy socket error: read ECONNRESET` happened

## Symptom
During local development, Vite logged repeated errors:

- `[vite] ws proxy socket error: Error: read ECONNRESET`

At the same time, backend logs showed multiple WebSocket disconnects at the same second:

- `WebSocket client disconnected (total: 3)`
- `WebSocket client disconnected (total: 2)`
- `WebSocket client disconnected (total: 1)`
- `WebSocket client disconnected (total: 0)`

HTTP API endpoints (like `GET /api/admin/logs`) still returned `200 OK`, so the backend itself was not crashing.

## Root cause
The frontend was opening multiple separate WebSocket connections to the same endpoint (`/ws/updates`) instead of sharing one connection.

Before the fix:

- `useProducts()` called `useWebSocket("/ws/updates")`
  - File: `frontend/src/hooks/useProducts.js`
- `useProductRequests()` called `useWebSocket("/ws/updates")`
  - File: `frontend/src/hooks/useProductRequests.js`
- Those hooks were used in multiple mounted areas (emulator context, admin panel, incoming tab), creating multiple concurrent WS clients.
- In development, `React.StrictMode` in `frontend/src/main.jsx` can trigger extra mount/unmount cycles, amplifying connect/disconnect churn.

When these sockets closed around the same moment (refresh/HMR/re-render/unmount), Vite’s WS proxy reported `ECONNRESET` for each dropped upstream socket.

## Why SQL logs looked noisy but unrelated
The SQLAlchemy/aiosqlite logs (`BEGIN`, `SELECT`, `ROLLBACK`) were from normal read-only polling (`/api/admin/logs`).
They were not the cause of the WS reset.

## Fix implemented
A shared singleton WebSocket manager was added inside:

- `frontend/src/hooks/useWebSocket.js`

What changed:

- One socket per URL is stored in a module-level map.
- Multiple hook consumers subscribe to the same shared socket.
- Reference counting tracks active subscribers.
- Reconnect runs only while subscribers exist.
- A short close grace period reduces StrictMode churn disconnect noise.

## Expected result after fix

- Far fewer repeated `ECONNRESET` messages in Vite logs.
- Backend WS client count should stay near one active connection per page context (instead of growing with each hook consumer).
- Occasional single disconnects can still happen during dev reload/HMR and are normal.
