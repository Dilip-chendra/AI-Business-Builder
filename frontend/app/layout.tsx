import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/AppShell";
import { ActiveContextProvider } from "@/lib/active-context";
import { AuthProvider } from "@/lib/auth-context";
import { ToastProvider } from "@/components/Toast";
import { SWRProvider } from "@/lib/swr-config";

export const metadata: Metadata = {
  title: "AI Business Builder",
  description: "Generate, launch, monetize, and optimize online businesses with AI.",
  icons: {
    icon: [
      { url: "/brand/abb-icon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/brand/abb-icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/brand/abb-icon-180.png", sizes: "180x180", type: "image/png" }],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <SWRProvider>
          <AuthProvider>
            <ActiveContextProvider>
              <ToastProvider>
                <AppShell>{children}</AppShell>
              </ToastProvider>
            </ActiveContextProvider>
          </AuthProvider>
        </SWRProvider>
      </body>
    </html>
  );
}
