"use client";

import { ReactNode, useState } from "react";
import { Button } from "@/components/Button";
import { api } from "@/lib/api";

export function CheckoutButton({ productId, children }: { productId: string; children: ReactNode }) {
  const [loading, setLoading] = useState(false);
  async function checkout() {
    setLoading(true);
    try {
      const session = await api.createCheckout(productId);
      window.location.href = session.checkout_url;
    } finally {
      setLoading(false);
    }
  }
  return (
    <Button onClick={checkout} disabled={loading}>
      {loading ? "Opening..." : children}
    </Button>
  );
}
