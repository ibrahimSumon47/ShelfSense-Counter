import React from 'react';
import './globals.css';

export const metadata = {
  title: 'ShelfSense — Retail Shelf Inventory Counter',
  description: 'Count retail shelf products, detect empty stock gaps, and query scan history in English and Bangla.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
