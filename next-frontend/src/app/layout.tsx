import type { Metadata } from "next";
import { Instrument_Sans } from "next/font/google";
import "./globals.css";
import { Sidebar } from "../components/layout/Sidebar";
import { TopBar } from "../components/layout/TopBar";
import { FilterBar } from "../components/filters/FilterBar";
import { QueryProvider } from "../components/providers/QueryProvider";
import { MobileMenuProvider } from "../components/providers/MobileMenuProvider";
import { Suspense } from "react";

const instrumentSans = Instrument_Sans({ 
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-instrument",
});

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "ISRO SOC Dashboard",
  description: "Next-generation threat intelligence analytics",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${instrumentSans.variable} font-sans bg-background text-foreground flex h-screen overflow-hidden`}>
        <QueryProvider>
          <MobileMenuProvider>
            <Sidebar />
            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
              <TopBar />
              <Suspense fallback={<div className="h-10 bg-card border-b border-border p-2" />}>
                <FilterBar />
              </Suspense>
              <main className="flex-1 overflow-y-auto relative z-0 p-4 sm:p-6 lg:p-8">
                <div className="mx-auto max-w-7xl w-full">
                  <Suspense fallback={<div className="flex h-full items-center justify-center p-12">Loading content...</div>}>
                    {children}
                  </Suspense>
                </div>
              </main>
            </div>
          </MobileMenuProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
