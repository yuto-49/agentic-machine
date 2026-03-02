# Claudius Frontend — UI/UX Guide

React 18 + Vite + TailwindCSS PWA served on iPad as the customer-facing POS.

## Running Locally

```bash
cd frontend
npm install
npm run dev       # dev server with HMR
npm run build     # production build → dist/
```

The dev server proxies `/api` and `/ws` to `http://localhost:8000` (the FastAPI backend).

---

## Layout

```
+------------------------------------------+
|              CLAUDIUS                     |  <- indigo-600 header
|         AI Vending Machine               |
+------------------------------------------+
| Products | Cart (3) | Status | Incoming  |  <- tab bar (white bg, indigo active)
+------------------------------------------+
|                                          |
|             [ Tab Content ]              |  <- gray-100 bg, max-w-4xl centered
|                                          |
+------------------------------------------+
```

- 4 tabs: **Products**, **Cart**, **Status**, **Incoming**
- Cart tab shows a badge with the total item count when non-empty
- Active tab has an indigo-600 underline; inactive tabs are gray-500

---

## Tab 1 — Products

The main catalog grid. Fetches from `GET /api/products` on mount, then receives live WebSocket patches (`stock_update`, `price_update`) so quantities and prices stay current without a page refresh.

```
+------------------------------------------+
| Products | Cart | Status | Incoming      |
+------------------------------------------+
|                                          |
|  +----------+  +----------+  +--------+  |
|  |   [A1]   |  |   [A2]   |  |  [A3]  |  |
|  |          |  |          |  |        |  |
|  | Pocky    |  | Kit Kat  |  | Coke   |  |
|  | snack    |  | snack    |  | drink  |  |
|  | $2.50    |  | $1.75    |  | $1.50  |  |
|  | 8 in stk |  | 0 in stk |  | 5 in.. |  |
|  |          |  |          |  |        |  |
|  |[Add Cart]|  |[Sold Out]|  |[Add ..]|  |
|  +----------+  +----------+  +--------+  |
|                                          |
+------------------------------------------+
```

### Card anatomy

| Element | Style |
|---------|-------|
| Slot placeholder | gray-200 rounded box, 128px tall, slot label centered |
| Product name | font-semibold, gray-800 |
| Category | text-sm, gray-500 |
| Price | text-lg, font-bold, indigo-600 |
| Stock | text-xs, gray-400 ("8 in stock" or "Out of stock") |
| Add to Cart button | indigo-600 rounded, full width, bottom of card |
| Sold Out button | gray-300, cursor-not-allowed, disabled |

### Grid layout

- **Mobile (< md):** 2 columns
- **Desktop (>= md):** 3 columns
- Gap: 1rem (gap-4)

---

## Tab 2 — Cart

Shows selected items with per-line totals, a grand total, and a checkout button. Posts to `POST /api/cart/checkout`.

### Empty state

```
+------------------------------------------+
| Products | Cart | Status | Incoming      |
+------------------------------------------+
|                                          |
|         Your cart is empty.              |
|                                          |
+------------------------------------------+
```

### With items

```
+------------------------------------------+
| Products | Cart (2) | Status | Incoming  |
+------------------------------------------+
|                                          |
|  +--------------------------------------+|
|  | Pocky              $2.50 x 2  $5.00  ||
|  |                             [Remove] ||
|  |--------------------------------------||
|  | Coke               $1.50 x 1  $1.50  ||
|  |                             [Remove] ||
|  +--------------------------------------+|
|                                          |
|  Total: $6.50            [ Checkout ]    |
|                                          |
+------------------------------------------+
```

### Checkout result

- **Success:** green-100 banner with message, cart auto-clears
- **Failure:** red-100 banner with error detail

---

## Tab 3 — Status

Machine health check from `GET /api/status`.

```
+------------------------------------------+
| Products | Cart | Status | Incoming      |
+------------------------------------------+
|                                          |
|  +--------------------------------------+|
|  | Machine Status                       ||
|  |                                      ||
|  |  * Online                            ||
|  |                                      ||
|  |  Version       0.1.0                 ||
|  |  Environment   development           ||
|  +--------------------------------------+|
|                                          |
+------------------------------------------+
```

| Element | Detail |
|---------|--------|
| Status dot | green-500 circle if online, red-500 if offline |
| Info grid | 2-column `<dl>` — Version, Environment |

---

## Tab 4 — Incoming (NEW)

Customer product requests created via the Slack/Discord agent flow. Fetches from `GET /api/requests` on mount and receives live `new_product_request` WebSocket events.

### Empty state

```
+------------------------------------------+
| Products | Cart | Status | Incoming      |
+------------------------------------------+
|                                          |
|  No product requests yet.               |
|  Ask Claudius on Slack to find something!|
|                                          |
+------------------------------------------+
```

### With requests

```
+------------------------------------------+
| Products | Cart | Status | Incoming      |
+------------------------------------------+
|                                          |
|  +------------------+ +------------------+
|  | +----+           | | +----+           |
|  | |img | Monster   | | |img | Pocky     |
|  | |    | Energy    | | |    | Premium   |
|  | +----+ $8.49     | | +----+ $9.37     |
|  |  by @alice       | |  by @bob        |
|  |  via slack       | |  via slack      |
|  |                  | |                  |
|  | [pending] View ->| | [arrived] View->|
|  +------------------+ +------------------+
|                                          |
+------------------------------------------+
```

### Card anatomy

| Element | Style |
|---------|-------|
| Product image | 80x80px rounded thumbnail (left side) |
| Product name | font-semibold, gray-900, truncated |
| Estimated price | indigo-600, font-medium |
| Requester info | text-xs, gray-500 ("Requested by @alice via slack") |
| Status badge | rounded-full pill, color-coded (see below) |
| Source link | text-xs, indigo-500, opens in new tab |

### Status badge colors

| Status | Background | Text |
|--------|-----------|------|
| `pending` | yellow-100 | yellow-800 |
| `approved` | blue-100 | blue-800 |
| `ordered` | purple-100 | purple-800 |
| `arrived` | green-100 | green-800 |

### Grid layout

- **Mobile (< sm):** 1 column
- **Tablet+ (>= sm):** 2 columns
- Gap: 1rem (gap-4)

---

## Data Flow: Online Product Request

```
Slack user: "Can you find me Monster Energy?"
  |
  v
Agent calls search_product_online("Monster Energy")
  |
  v
MockSearchBackend returns 5 results sorted by price
  |
  v
Agent shows numbered results to user in Slack
  |
  v
User: "Get me the second one"
  |
  v
Agent calls request_online_product(...)
  |
  v
Guardrails check: price <= $150? name non-empty? -> allowed
  |
  v
ProductRequest row created in SQLite
  |
  v
WebSocket broadcast: { type: "new_product_request", request: {...} }
  |
  v
Incoming tab updates live (no page refresh needed)
```

---

## Real-Time Updates (WebSocket)

All tabs share the same WebSocket connection at `ws://host/ws/updates`.

| Event type | Affected tab | Behavior |
|------------|-------------|----------|
| `stock_update` | Products | Updates quantity for a single product card |
| `price_update` | Products | Updates displayed price for a single product card |
| `new_product_request` | Incoming | Prepends new request card to the list |
| `pong` | (internal) | Keep-alive response, not displayed |

Auto-reconnects after 3 seconds on disconnect.

---

## Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| indigo-600 | `#4F46E5` | Header, active tab, prices, buttons, links |
| indigo-700 | `#4338CA` | Button hover |
| gray-100 | `#F3F4F6` | Page background |
| gray-200 | `#E5E7EB` | Product image placeholder |
| gray-500 | `#6B7280` | Inactive tabs, secondary text |
| green-500 | `#22C55E` | Online status dot |
| red-500 | `#EF4444` | Offline status dot, error text |
| white | `#FFFFFF` | Cards, tab bar |

---

## File Structure

```
frontend/
  src/
    App.jsx                         <- Shell: header + tab nav + tab router
    components/
      ProductGrid.jsx               <- Tab 1: product catalog grid
      Cart.jsx                      <- Tab 2: cart items + checkout
      MachineStatus.jsx             <- Tab 3: health check
      IncomingTab.jsx               <- Tab 4: requested products (NEW)
    hooks/
      useProducts.js                <- Fetch + WS patches for products
      useProductRequests.js         <- Fetch + WS patches for requests (NEW)
      useWebSocket.js               <- Shared WS connection hook
      useAgentLogs.js               <- Agent decision log viewer
```
