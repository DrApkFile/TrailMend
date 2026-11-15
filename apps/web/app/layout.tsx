import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Footer, Header } from "@/components/site/Header";

export const metadata: Metadata = {
  title: "TrailMend — every answer leaves a trail",
  description:
    "A graph on HydraDB that learns from its own answers: it reprices the links an answer walked, quarantines the ones that keep being wrong, and keeps a receipt for every change.",
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
