import type {
  Metadata,
} from "next";

import "@/app/globals.css";
import "@/app/auth-hardening.css";
import "@/app/operations-hardening.css";


export const metadata: Metadata = {
  title: {
    default:
      "DocuFlow AP Operations",
    template:
      "%s | DocuFlow AP",
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
