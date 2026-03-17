import type { Metadata } from "next";
import { APP_DASHBOARD_TITLE } from "@/lib/branding";
import "./globals.css";

export const metadata: Metadata = {
  title: APP_DASHBOARD_TITLE,
  description: "View your pet's preventive health records and reminders",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Fraunces:wght@700;900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
