import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Share_Tech_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/lib/providers";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains-mono",
});

const shareTechMono = Share_Tech_Mono({
  weight: "400",
  subsets: ["latin"],
  display: "swap",
  variable: "--font-share-tech-mono",
});

export const metadata: Metadata = {
  title: "TRACE-X | Cryptocurrency Fraud Investigation Platform",
  description: "Real-Time Cryptocurrency Fraud Attribution & Investigation Platform",
  keywords: ["cryptocurrency", "fraud", "investigation", "blockchain", "forensics", "law enforcement"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} ${shareTechMono.variable} antialiased`}
    >
      <body className="min-h-screen bg-background font-sans text-foreground">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}