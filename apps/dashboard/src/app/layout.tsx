import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { GeistPixelCircle } from "geist/font/pixel";
import "lenis/dist/lenis.css";
import "./globals.css";
import landing from "@/content/landing.json";
import { themeBootScript } from "@/lib/prototypeKeys";

export const metadata: Metadata = {
  title: { default: landing.meta.title, template: landing.meta.titleTemplate },
  description: landing.meta.description,
};

export const viewport: Viewport = {
  themeColor: landing.meta.themeColor,
  colorScheme: "dark",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable} ${GeistPixelCircle.variable} antialiased`}
      // The boot script may set data-console-theme before hydration.
      suppressHydrationWarning
    >
      <head>
        {/* Static, build-time constant (no user input): applies the saved console theme before paint. */}
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
