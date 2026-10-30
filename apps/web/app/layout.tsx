import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";


export const metadata: Metadata = {
  title: "Enya Local 3D Studio",
  description: "Local-first image-to-3D generation MVP with FastAPI, Next.js, Redis/RQ, and pluggable backends."
};


export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

