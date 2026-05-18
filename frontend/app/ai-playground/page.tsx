"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
export default function AIPlaygroundRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/ai-studio"); }, [router]);
  return null;
}
