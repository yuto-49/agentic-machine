import React, { useEffect, useState } from "react";

export default function ProductGrid({ onAddToCart }) {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

  if (loading) return <p className="text-center py-8 text-gray-500">Loading products...</p>;
  if (error) return <p className="text-center py-8 text-red-500">Error: {error}</p>;
  if (products.length === 0) return <p className="text-center py-8 text-gray-500">No products available.</p>;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
      {products.map((product) => (
        <div
          key={product.id}
          className="bg-white rounded-lg shadow p-4 flex flex-col"
        >
          {/* Placeholder for product image */}
          <div className="bg-gray-200 rounded h-32 mb-3 flex items-center justify-center text-gray-400 text-sm">
            {product.slot}
          </div>

          <h3 className="font-semibold text-gray-800">{product.name}</h3>
          <p className="text-sm text-gray-500 mb-1">{product.category}</p>
          <p className="text-lg font-bold text-indigo-600 mb-2">
            ${product.sell_price.toFixed(2)}
          </p>
          <p className="text-xs text-gray-400 mb-3">
            {product.quantity > 0
              ? `${product.quantity} in stock`
              : "Out of stock"}
          </p>

          <button
            onClick={() => onAddToCart(product)}
            disabled={product.quantity === 0}
            className={`mt-auto py-2 rounded text-white font-medium ${
              product.quantity > 0
                ? "bg-indigo-600 hover:bg-indigo-700"
                : "bg-gray-300 cursor-not-allowed"
            }`}
          >
            {product.quantity > 0 ? "Add to Cart" : "Sold Out"}
          </button>
        </div>
      ))}
    </div>
  );
}
