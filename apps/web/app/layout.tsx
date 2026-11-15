import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Shell";

export const metadata: Metadata = {
  title: "TrailMend",
  description: "The graph that repairs its own relationships.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-stone-950 text-stone-100 antialiased">
        <div className="mx-auto w-full max-w-3xl px-4 py-10">
          <Nav />
          {children}
        </div>
      </body>
    </html>
  );
}
