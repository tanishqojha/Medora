import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const inter = Inter({ variable: "--ff-inter", subsets: ["latin"] });
const jakarta = Plus_Jakarta_Sans({ variable: "--ff-jakarta", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Medora",
  description: "Follow-up copilot for cancer-care coordinators. Synthetic data only.",
  icons: { icon: "/logo.png" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        {/* Icon font: display=block on purpose, so icon names never flash as text. */}
        {/* eslint-disable-next-line @next/next/no-page-custom-font, @next/next/google-font-display */}
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block"
        />
      </head>
      <body className={`${inter.variable} ${jakarta.variable} bg-background font-body-md text-on-surface antialiased`}>
        {children}
      </body>
    </html>
  );
}
