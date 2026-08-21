import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ResolveAI",
  description: "AI customer-support copilot",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
