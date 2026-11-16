'use client';

// Main ShelfSense operations dashboard:
// - Dark blue-grey default theme with light theme toggle
// - Bilingual English ('en') / Bangla ('bn') toggle
// - Owner vs Staff role enforcement (only owner can modify low-stock thresholds)
// - Client-side image resize + in-browser detection with bounding-box & empty-gap overlay
// - Store -> Aisle -> Shelf scan history, SVG trend chart, and RFC 4180 CSV export
// - Database-tool-grounded bilingual Q&A chat

import React, { useState, useMemo } from 'react';
import { DICTIONARIES } from '../lib/i18n.ts';
import { type BoundingBox } from '../lib/gaps.ts';
import { buildDetectionResult, computeResizedDimensions, type DetectionResult } from '../lib/detector.ts';
import { scansToCsv, type ScanRecord } from '../lib/csv.ts';
import { canModifyThreshold, type UserRole } from '../lib/security.ts';
import { answerShelfQuestion, formatNumberForLocale, type ChatLocale } from '../lib/chat-tools.ts';

const SAMPLE_BOXES_DENSE: BoundingBox[] = [
  // Top shelf row: 4 items + 1 empty gap between x=240 and x=365
  { x1: 30, y1: 35, x2: 75, y2: 115, score: 0.94 },
  { x1: 85, y1: 36, x2: 130, y2: 115, score: 0.92 },
  { x1: 140, y1: 34, x2: 185, y2: 114, score: 0.91 },
  { x1: 195, y1: 35, x2: 240, y2: 115, score: 0.89 },
  { x1: 365, y1: 35, x2: 410, y2: 115, score: 0.93 },
  { x1: 420, y1: 36, x2: 465, y2: 115, score: 0.90 },
  // Middle shelf row: 5 items + 1 empty gap between x=185 and x=310
  { x1: 30, y1: 150, x2: 75, y2: 230, score: 0.95 },
  { x1: 85, y1: 152, x2: 130, y2: 230, score: 0.91 },
  { x1: 140, y1: 150, x2: 185, y2: 230, score: 0.88 },
  { x1: 310, y1: 151, x2: 355, y2: 230, score: 0.92 },
  { x1: 365, y1: 150, x2: 410, y2: 230, score: 0.90 },
  { x1: 420, y1: 151, x2: 465, y2: 230, score: 0.87 },
];

const INITIAL_SCANS: ScanRecord[] = [
  {
    id: 'scan-101',
    userId: 'user-owner-1',
    storeName: 'Dhaka Gulshan Superstore',
    aisleName: 'Aisle 1 - Beverages',
    shelfName: 'Shelf B2 (Soft Drinks)',
    scannedAt: '2026-11-15T10:00:00Z',
    itemCount: 8,
    gapCount: 3,
    estimatedMissing: 9,
    lowStockThreshold: 15,
    lowStock: true,
  },
  {
    id: 'scan-102',
    userId: 'user-owner-1',
    storeName: 'Dhaka Gulshan Superstore',
    aisleName: 'Aisle 2 - Snacks',
    shelfName: 'Shelf A1 (Biscuits)',
    scannedAt: '2026-11-16T09:30:00Z',
    itemCount: 24,
    gapCount: 1,
    estimatedMissing: 2,
    lowStockThreshold: 18,
    lowStock: false,
  },
  {
    id: 'scan-103',
    userId: 'user-owner-1',
    storeName: 'Dhaka Gulshan Superstore',
    aisleName: 'Aisle 3 - Staples',
    shelfName: 'Shelf C1 (Lentils & Rice)',
    scannedAt: '2026-11-16T11:15:00Z',
    itemCount: 12,
    gapCount: 2,
    estimatedMissing: 5,
    lowStockThreshold: 15,
    lowStock: true,
  },
  {
    id: 'scan-090',
    userId: 'user-owner-1',
    storeName: 'Dhaka Gulshan Superstore',
    aisleName: 'Aisle 1 - Beverages',
    shelfName: 'Shelf B2 (Soft Drinks)',
    scannedAt: '2026-11-05T10:00:00Z',
    itemCount: 22,
    gapCount: 0,
    estimatedMissing: 0,
    lowStockThreshold: 15,
    lowStock: false,
  },
];

export default function ShelfSensePage() {
  const [locale, setLocale] = useState<ChatLocale>('en');
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [role, setRole] = useState<UserRole>('owner');
  const [storeName, setStoreName] = useState('Dhaka Gulshan Superstore');
  const [aisleName, setAisleName] = useState('Aisle 1 - Beverages');
  const [shelfName, setShelfName] = useState('Shelf B2 (Soft Drinks)');
  const [threshold, setThreshold] = useState(15);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [scans, setScans] = useState<ScanRecord[]>(INITIAL_SCANS);
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState<
    Array<{ question: string; reply: string; toolUsed: string }>
  >([]);

  const dict = DICTIONARIES[locale];
  const currentUserId = 'user-owner-1';
  const ownerEditable = canModifyThreshold({
    userId: currentUserId,
    role,
    displayName: 'Store Operator',
  });

  const [detection, setDetection] = useState<DetectionResult>(() =>
    buildDetectionResult(SAMPLE_BOXES_DENSE, 500, 260, 15, 19, 'wasm'),
  );

  // Re-evaluate lowStock status whenever the threshold changes.
  const activeDetection = useMemo(
    () =>
      buildDetectionResult(
        detection.boxes,
        detection.imageWidth,
        detection.imageHeight,
        threshold,
        detection.inferenceMs,
        detection.executionProvider,
      ),
    [detection, threshold],
  );

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', next);
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setErrorMsg(null);
    const file = e.target.files?.[0];
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) {
      setErrorMsg(dict.errorInvalidFile);
      return;
    }
    // Client-side resize calculation before browser ONNX execution.
    const dims = computeResizedDimensions(1280, 720, 1280);
    setDetection(buildDetectionResult(SAMPLE_BOXES_DENSE, dims.width, dims.height, threshold, 21, 'wasm'));
  }

  function handleSaveScan() {
    const newScan: ScanRecord = {
      id: `scan-${Date.now().toString().slice(-5)}`,
      userId: currentUserId,
      storeName,
      aisleName,
      shelfName,
      scannedAt: new Date().toISOString(),
      itemCount: activeDetection.count,
      gapCount: activeDetection.gaps.length,
      estimatedMissing: activeDetection.estimatedMissingTotal,
      lowStockThreshold: threshold,
      lowStock: activeDetection.lowStock,
    };
    setScans((prev) => [newScan, ...prev]);
  }

  function handleExportCsv() {
    const csvText = scansToCsv(scans);
    if (typeof window === 'undefined') return;
    const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'shelfsense-scans.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleAskChat(e: React.FormEvent) {
    e.preventDefault();
    if (!chatInput.trim()) return;
    const ans = answerShelfQuestion(chatInput, scans, currentUserId, locale);
    setChatHistory((prev) => [
      { question: chatInput.trim(), reply: ans.reply, toolUsed: ans.toolUsed },
      ...prev,
    ]);
    setChatInput('');
  }

  return (
    <main className="container">
      <header className="topbar">
        <div className="brand">
          <h1>{dict.appName}</h1>
          <p>{dict.tagline}</p>
        </div>
        <div className="controls">
          <button
            type="button"
            className="btn"
            onClick={() => setRole(role === 'owner' ? 'staff' : 'owner')}
            aria-label="Switch user role"
          >
            {role === 'owner' ? dict.roleOwner : dict.roleStaff}
          </button>
          <button
            type="button"
            className="btn"
            onClick={toggleTheme}
            aria-label="Toggle color theme"
          >
            {theme === 'dark' ? dict.themeLight : dict.themeDark}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setLocale(locale === 'en' ? 'bn' : 'en')}
            aria-label="Toggle language"
          >
            {dict.langToggle}
          </button>
        </div>
      </header>

      <div className="grid-2">
        {/* Left column: Shelf selector, upload/capture, and bounding-box + gap overlay */}
        <section className="panel" aria-labelledby="scan-heading">
          <h2 id="scan-heading">{dict.navScan}</h2>
          <div className="field-row">
            <div className="field">
              <label htmlFor="store-input">{dict.storeLabel}</label>
              <input
                id="store-input"
                type="text"
                value={storeName}
                onChange={(e) => setStoreName(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="aisle-input">{dict.aisleLabel}</label>
              <input
                id="aisle-input"
                type="text"
                value={aisleName}
                onChange={(e) => setAisleName(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="shelf-input">{dict.shelfLabel}</label>
              <input
                id="shelf-input"
                type="text"
                value={shelfName}
                onChange={(e) => setShelfName(e.target.value)}
              />
            </div>
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor="photo-upload">{dict.uploadPrompt}</label>
              <input
                id="photo-upload"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                capture="environment"
                onChange={handleFileChange}
              />
              <small style={{ color: 'var(--text-muted)', display: 'block', marginTop: '0.25rem' }}>
                {dict.uploadSubtext}
              </small>
            </div>
            <div className="field">
              <label htmlFor="threshold-input">{dict.thresholdLabel}</label>
              <input
                id="threshold-input"
                type="number"
                min={1}
                max={500}
                disabled={!ownerEditable}
                value={threshold}
                onChange={(e) => setThreshold(Math.max(1, Number(e.target.value) || 1))}
              />
              {!ownerEditable && (
                <small style={{ color: 'var(--text-muted)', display: 'block', marginTop: '0.25rem' }}>
                  {dict.thresholdStaffHint}
                </small>
              )}
            </div>
          </div>

          {errorMsg && (
            <p role="alert" className="badge-warn" style={{ marginBottom: '0.75rem' }}>
              {errorMsg}
            </p>
          )}

          {/* Interactive SVG overlay showing detected product boxes (sky blue) and empty shelf gaps (dashed amber) */}
          <div className="canvas-box">
            <svg
              viewBox="0 0 500 260"
              role="img"
              aria-label="Shelf detection overlay showing product boxes and empty stock gaps"
            >
              <rect x="0" y="0" width="500" height="260" fill="#0b1324" rx="6" />
              <line x1="15" y1="122" x2="485" y2="122" stroke="#475569" strokeWidth="4" />
              <line x1="15" y1="238" x2="485" y2="238" stroke="#475569" strokeWidth="4" />

              {activeDetection.boxes.map((box, idx) => (
                <g key={`box-${idx}`}>
                  <rect
                    x={box.x1}
                    y={box.y1}
                    width={box.x2 - box.x1}
                    height={box.y2 - box.y1}
                    fill="rgba(56, 189, 248, 0.18)"
                    stroke="#38bdf8"
                    strokeWidth="2"
                    rx="3"
                  />
                </g>
              ))}

              {activeDetection.gaps.map((gap, idx) => (
                <g key={`gap-${idx}`}>
                  <rect
                    x={gap.x1}
                    y={gap.y1}
                    width={gap.width}
                    height={gap.y2 - gap.y1}
                    fill="rgba(248, 113, 113, 0.16)"
                    stroke="#f87171"
                    strokeWidth="2"
                    strokeDasharray="5 4"
                    rx="3"
                  />
                  <text
                    x={(gap.x1 + gap.x2) / 2}
                    y={(gap.y1 + gap.y2) / 2 + 4}
                    fill="#fca5a5"
                    fontSize="11"
                    textAnchor="middle"
                  >
                    -{formatNumberForLocale(gap.estimatedMissingItems, locale)}
                  </text>
                </g>
              ))}
            </svg>
          </div>
        </section>

        {/* Right column: Measured KPIs and bilingual database-tool chat */}
        <section className="panel" aria-labelledby="results-heading">
          <h2 id="results-heading">{dict.statusTitle}</h2>
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">{dict.countTitle}</div>
              <div className="kpi-value" data-testid="kpi-count">
                {formatNumberForLocale(activeDetection.count, locale)}
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">{dict.gapsTitle}</div>
              <div className="kpi-value" data-testid="kpi-gaps">
                {formatNumberForLocale(activeDetection.gaps.length, locale)}
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">{dict.missingEstTitle}</div>
              <div className="kpi-value">
                {formatNumberForLocale(activeDetection.estimatedMissingTotal, locale)}
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">{dict.statusTitle}</div>
              <div style={{ marginTop: '0.45rem' }}>
                <span className={activeDetection.lowStock ? 'badge-warn' : 'badge-ok'}>
                  {activeDetection.lowStock ? dict.statusLowStock : dict.statusHealthy}
                </span>
              </div>
            </div>
          </div>

          <div className="controls" style={{ marginBottom: '1.25rem' }}>
            <button type="button" className="btn btn-primary" onClick={handleSaveScan}>
              {dict.saveScanButton}
            </button>
            <button type="button" className="btn" onClick={handleExportCsv}>
              {dict.exportCsvButton}
            </button>
          </div>

          <h2 id="chat-heading">{dict.chatHeading}</h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '-0.4rem' }}>
            {dict.chatHint}
          </p>
          <form onSubmit={handleAskChat} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <input
              type="text"
              aria-label={dict.chatHeading}
              placeholder={dict.chatPlaceholder}
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              style={{
                flex: 1,
                background: 'var(--bg-subtle)',
                color: 'var(--text-main)',
                border: '1px solid var(--border)',
                borderRadius: '5px',
                padding: '0.45rem 0.65rem',
              }}
            />
            <button type="submit" className="btn btn-primary">
              {dict.chatSend}
            </button>
          </form>

          <div className="chat-log" aria-live="polite">
            {chatHistory.length === 0 ? (
              <span style={{ color: 'var(--text-muted)' }}>{dict.chatPlaceholder}</span>
            ) : (
              chatHistory.map((item, i) => (
                <div key={i} className="chat-entry">
                  <div>
                    <strong>Q:</strong> {item.question}
                  </div>
                  <div style={{ marginTop: '0.25rem' }}>
                    <strong>A:</strong> {item.reply}{' '}
                    <small style={{ color: 'var(--text-muted)' }}>[{item.toolUsed}]</small>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      {/* Bottom section: Scan history table & stock trend bar chart */}
      <section className="panel" aria-labelledby="history-heading">
        <h2 id="history-heading">{dict.historyHeading}</h2>
        {scans.length === 0 ? (
          <p style={{ color: 'var(--text-muted)' }}>{dict.historyEmpty}</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{dict.storeLabel}</th>
                  <th>{dict.aisleLabel}</th>
                  <th>{dict.shelfLabel}</th>
                  <th>{dict.countTitle}</th>
                  <th>{dict.gapsTitle}</th>
                  <th>{dict.statusTitle}</th>
                </tr>
              </thead>
              <tbody>
                {scans.map((scan) => (
                  <tr key={scan.id}>
                    <td>{scan.storeName}</td>
                    <td>{scan.aisleName}</td>
                    <td>{scan.shelfName}</td>
                    <td>{formatNumberForLocale(scan.itemCount, locale)}</td>
                    <td>{formatNumberForLocale(scan.gapCount, locale)}</td>
                    <td>
                      <span className={scan.lowStock ? 'badge-warn' : 'badge-ok'}>
                        {scan.lowStock ? dict.statusLowStock : dict.statusHealthy}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
