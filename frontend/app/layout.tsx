import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/AppShell";
import { ActiveContextProvider } from "@/lib/active-context";
import { AuthProvider } from "@/lib/auth-context";
import { ToastProvider } from "@/components/Toast";
import { SWRProvider } from "@/lib/swr-config";

export const metadata: Metadata = {
  title: "Autonomous Business Builder",
  description: "Generate, launch, monetize, and optimize online businesses with AI.",
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
