import "./globals.css";

export const metadata = {
  title: "Resume Parser",
  description: "Upload a PDF resume and inspect the parsed candidate profile."
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
