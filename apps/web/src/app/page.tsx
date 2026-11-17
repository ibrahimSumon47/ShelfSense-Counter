'use client';

// ShelfSense operations dashboard.
// While MODEL_AVAILABLE is false (until Step 3 wires in the trained ONNX detector),
// the scan button and photo upload are disabled and the interface displays
// "not measured yet; pipeline demonstration only" with zero fake detection boxes.
// All real UI features (Store/Aisle/Shelf fields, owner/staff role guard, client resize
// handler, SVG overlay renderer, scan history table, trend chart, CSV export, and
// database-tool chat) remain intact and ready for Step 3.

import React, { useState } from 'react';
import { DICTIONARIES } from '../lib/i18n.ts';
import { computeResizedDimensions, type DetectionResult } from '../lib/detector.ts';
import { scansToCsv, type ScanRecord } from '../lib/csv.ts';
import { canModifyThreshold, type UserRole } from '../lib/security.ts';
import { answerShelfQuestion, formatNumberForLocale, type ChatLocale } from '../lib/chat-tools.ts';

// Set to true only in Step 3 when the real trained ONNX detector is loaded.
const MODEL_AVAILABLE = false;

export default function ShelfSensePage() {
  const [locale, setLocale] = useState<ChatLocale>('en');
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [role, setRole] = useState<UserRole>('owner');
  const [storeName, setStoreName] = useState('');
  const [aisleName, setAisleName] = useState('');
  const [shelfName, setShelfName] = useState('');
  const [threshold, setThreshold] = useState(15);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [detection, setDetection] = useState<DetectionResult | null>(null);
  const [scans, setScans] = useState<ScanRecord[]>([]);
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
    if (!MODEL_AVAILABLE) {
      // Do not fabricate detections when no trained model is loaded.
      computeResizedDimensions(1280, 720, 1280);
      setDetection(null);
    }
  }

  function handleSaveScan() {
    if (!detection) return;
    const newScan: ScanRecord = {
      id: `scan-${Date.now().toString().slice(-5)}`,
      userId: currentUserId,
      storeName: storeName || 'Store 1',
      aisleName: aisleName || 'Aisle 1',
      shelfName: shelfName || 'Shelf 1',
      scannedAt: new Date().toISOString(),
      itemCount: detection.count,
      gapCount: detection.gaps.length,
      estimatedMissing: detection.estimatedMissingTotal,
      lowStockThreshold: threshold,
      lowStock: detection.count < threshold,
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
        <section className="panel" aria-labelledby="scan-heading">
          <h2 id="scan-heading">{dict.navScan}</h2>

          {!MODEL_AVAILABLE && (
            <div role="status" className="badge-warn" style={{ display: 'block', marginBottom: '0.85rem' }}>
              <strong>{dict.modelMissingTitle}.</strong> {dict.modelMissingBody}
            </div>
          )}

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
                disabled={!MODEL_AVAILABLE}
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

          {detection && (
            <div className="canvas-box">
              <svg
                viewBox={`0 0 ${detection.imageWidth} ${detection.imageHeight}`}
                role="img"
                aria-label="Shelf detection overlay"
              >
                {detection.boxes.map((box, idx) => (
                  <rect
                    key={`box-${idx}`}
                    x={box.x1}
                    y={box.y1}
                    width={box.x2 - box.x1}
                    height={box.y2 - box.y1}
                    fill="rgba(56, 189, 248, 0.18)"
                    stroke="#38bdf8"
                    strokeWidth="2"
                  />
                ))}
                {detection.gaps.map((gap, idx) => (
                  <rect
                    key={`gap-${idx}`}
                    x={gap.x1}
                    y={gap.y1}
                    width={gap.width}
                    height={gap.y2 - gap.y1}
                    fill="rgba(248, 113, 113, 0.16)"
                    stroke="#f87171"
                    strokeWidth="2"
                    strokeDasharray="5 4"
                  />
                ))}
              </svg>
            </div>
          )}
        </section>

        <section className="panel" aria-labelledby="results-heading">
          <h2 id="results-heading">{dict.statusTitle}</h2>
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">{dict.countTitle}</div>
              <div className="kpi-value" data-testid="kpi-count">
                {detection ? formatNumberForLocale(detection.count, locale) : '—'}
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">{dict.gapsTitle}</div>
              <div className="kpi-value" data-testid="kpi-gaps">
                {detection ? formatNumberForLocale(detection.gaps.length, locale) : '—'}
              </div>
            </div>
          </div>
          {!detection && (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{dict.noScanYet}</p>
          )}

          <div className="controls" style={{ marginBottom: '1.25rem' }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleSaveScan}
              disabled={!detection}
            >
              {dict.saveScanButton}
            </button>
            <button
              type="button"
              className="btn"
              onClick={handleExportCsv}
              disabled={scans.length === 0}
            >
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
