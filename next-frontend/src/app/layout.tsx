import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { LayoutDashboard, AlertTriangle, ShieldAlert, Activity, Search, Users, FileText, Settings } from "lucide-react";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ISRO SOC Next.js Dashboard",
  description: "Next-generation threat intelligence analytics",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-background text-foreground flex h-screen overflow-hidden`}>
        {/* Sidebar */}
        <aside className="w-64 flex-shrink-0 bg-card-bg border-r border-card-border flex flex-col">
          <div className="p-6 border-b border-card-border">
            <h1 className="text-xl font-bold tracking-wider text-white">ISRO<span className="text-accent">.</span>SOC</h1>
            <p className="text-xs text-gray-400 mt-1 uppercase tracking-widest">Command Center</p>
          </div>
          
          <nav className="flex-1 overflow-y-auto py-4">
            <ul className="space-y-1 px-3">
              {[
                { name: "Overview", href: "/dashboard", icon: LayoutDashboard },
                { name: "Anomalies", href: "/anomalies", icon: AlertTriangle },
                { name: "Threats", href: "/threats", icon: ShieldAlert },
                { name: "Behavior", href: "/behavior", icon: Activity },
                { name: "Investigations", href: "/investigations", icon: Search },
                { name: "Entities", href: "/entities", icon: Users },
                { name: "Reports", href: "/reports", icon: FileText },
              ].map((item) => (
                <li key={item.name}>
                  <Link href={item.href} className="flex items-center gap-3 px-3 py-2 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-md transition-colors">
                    <item.icon size={18} className="text-primary" />
                    {item.name}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          
          <div className="p-4 border-t border-card-border">
            <Link href="/settings" className="flex items-center gap-3 px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-white/5 rounded-md transition-colors">
              <Settings size={18} />
              Settings
            </Link>
          </div>
        </aside>

        {/* Main Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <header className="h-16 border-b border-card-border bg-card-bg/50 backdrop-blur flex items-center justify-between px-8">
            <div className="text-sm font-medium text-gray-400">System Status: <span className="text-green-500">Online</span></div>
            <div className="flex items-center gap-4">
              <span className="text-xs bg-primary/20 text-primary px-3 py-1 rounded-full border border-primary/30">Admin</span>
            </div>
          </header>
          
          <main className="flex-1 overflow-y-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
