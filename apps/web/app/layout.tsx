import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Footer, Header } from "@/components/site/Header";

export const metadata: Metadata = {
  title: "TrailMend — every answer leaves a trail",
  description:
    "Your service catalogue is quietly wrong. TrailMend finds out from its own answers and fixes it, with a receipt for every change.",
};

export const viewport: Viewport = {
  themeColor: "#0a0a0b",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-night text-ink antialiased">
        <Header />
        {children}
        <Footer />
      </body>
    </html>
  );
}
