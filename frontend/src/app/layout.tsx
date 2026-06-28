import Link from "next/link";
import "./globals.css";

const navigation = [
  ["Dashboard", "/"],
  ["Dramas", "/dramas"],
  ["Rights Holders", "/rights-holders"],
  ["License Requests", "/license-requests"],
  ["Trend Analyzer", "/trend-analyzer"],
  ["Automation Plan", "/automation-plan"],
  ["Script Review", "/script-review"],
  ["Render Queue", "/render-queue"],
  ["Upload Queue", "/upload-queue"],
  ["Compliance Logs", "/compliance-logs"]
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <aside>
          <div className="brand">DRAMA OPS</div>
          <p className="caption">YouTube Automation</p>
          <nav>
            {navigation.map(([label, href]) => (
              <Link key={href} href={href}>{label}</Link>
            ))}
          </nav>
        </aside>
        <main>{children}</main>
      </body>
    </html>
  );
}
