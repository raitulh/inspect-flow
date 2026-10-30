import type { Metadata, Viewport } from "next";
import AppShell from "@/components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "LineGuard CV — Manufacturing Intelligence",
  description: "Evidence-first manufacturing quality and station monitoring.",
  applicationName: "LineGuard CV",
};

export const viewport: Viewport = { themeColor: "#1e2524", colorScheme: "dark" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><AppShell>{children}</AppShell></body></html>;
}
