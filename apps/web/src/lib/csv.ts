// CSV export and RFC 4180 formula-injection sanitization for stored shelf scans.

export interface ScanRecord {
  id: string;
  userId: string;
  storeName: string;
  aisleName: string;
  shelfName: string;
  scannedAt: string; // ISO 8601 timestamp
  itemCount: number;
  gapCount: number;
  estimatedMissing: number;
  lowStockThreshold: number;
  lowStock: boolean;
  thumbnailUrl?: string;
}

// Escapes a single CSV field and neutralizes spreadsheet formula injection (`=`, `+`, `-`, `@`).
export function escapeCsvCell(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) return '';
  let str = String(value);
  if (/^[=+\-@]/.test(str) && !/^-\d+(\.\d+)?$/.test(str)) {
    str = `'${str}`;
  }
  if (/[",\r\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

// Converts an array of user-scoped ScanRecord entries into a downloadable CSV string.
export function scansToCsv(scans: ScanRecord[]): string {
  const headers = [
    'scan_id',
    'scanned_at',
    'store',
    'aisle',
    'shelf',
    'item_count',
    'gap_count',
    'estimated_missing',
    'low_stock_threshold',
    'low_stock',
  ];
  const rows = scans.map((s) =>
    [
      s.id,
      s.scannedAt,
      s.storeName,
      s.aisleName,
      s.shelfName,
      s.itemCount,
      s.gapCount,
      s.estimatedMissing,
      s.lowStockThreshold,
      s.lowStock,
    ]
      .map(escapeCsvCell)
      .join(','),
  );
  return [headers.join(','), ...rows].join('\n');
}
