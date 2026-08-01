import type { Metadata } from "next";
import "./globals.css";
import { AuthInitializer } from "./auth-initializer";

// Metadata is what shows up in the browser tab and search engines
export const metadata: Metadata = {
  title: "IELTS AI Coach | Master Your Exam",
  description: "Personalized IELTS coaching powered by AI for Writing and Speaking.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <AuthInitializer />
        {/* 
            The {children} is where your pages (like Home or Dashboard) 
            will be "injected" by Next.js.
        */}
        <main className="min-h-screen bg-slate-50">
          {children}
        </main>
      </body>
    </html>
  );
}
