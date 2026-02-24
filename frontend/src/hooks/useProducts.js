import { useEffect, useState } from "react";
import useWebSocket from "./useWebSocket";

/**
 * Fetches products from /api/products on mount, then applies
 * real-time WebSocket patches for stock and price changes.
 */
export default function useProducts() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { lastMessage, isConnected } = useWebSocket("/ws/updates");

  useEffect(() => {
    fetch("/api/products")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(setProducts)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  // Apply WebSocket updates to product list
  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === "stock_update") {
      setProducts((prev) =>
        prev.map((p) =>
          p.id === lastMessage.product_id
            ? { ...p, quantity: lastMessage.quantity }
            : p
        )
      );
    }

    if (lastMessage.type === "price_update") {
      setProducts((prev) =>
        prev.map((p) =>
          p.id === lastMessage.product_id
            ? { ...p, sell_price: lastMessage.sell_price }
            : p
        )
      );
    }
  }, [lastMessage]);

  return { products, setProducts, loading, error, wsConnected: isConnected };
}
