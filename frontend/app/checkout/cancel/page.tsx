import Link from "next/link";
import { Button } from "@/components/Button";

export default function CheckoutCancelPage() {
  return (
    <div className="mx-auto max-w-xl rounded border border-stone-200 bg-white p-8 text-center shadow-soft">
      <h1 className="text-3xl font-semibold">Checkout canceled</h1>
      <p className="mt-3 text-stone-600">No payment was captured.</p>
      <Link href="/dashboard" className="mt-6 inline-block">
        <Button variant="secondary">Back to dashboard</Button>
      </Link>
    </div>
  );
}
