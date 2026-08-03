import type { Metadata } from "next";

import "@/app/globals.css";


export const metadata: Metadata = {
  title: {
    default: "DocuFlow AP Operations",
    template: "%s | DocuFlow AP",
  },
  description:
    "Accounts payable automation operations dashboard.",
};


export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
