import "./globals.css";

export const metadata = {
  title: "ResumeRank ATS Workspace",
  description: "Enterprise ATS dashboard for parsing, ranking, filtering, and reviewing resumes."
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
