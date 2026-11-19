'use client';

// ShelfSense operations dashboard.
// Inference runs in this browser with onnxruntime-web (WebGPU when the browser has it, WASM
// otherwise). The model file is published next to the app, and `/models/manifest.json` says
// which file to load and which score/NMS thresholds were tuned on validation.
// If no model is published the photo controls stay disabled and the page says so, rather
// than showing invented boxes.

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { DICTIONARIES } from '../lib/i18n.ts';
import {
  DEFAULT_DETECTOR_PARAMS,
  buildDetectionResult,
  computeResizedDimensions,
  loadOnnxDetector,
  runFcosDetection,
  type DetectionResult,
  type DetectorParams,
  type FcosPreprocessing,
  MODERN_PREPROCESSING,
} from '../lib/detector.ts';
import { scansToCsv, type ScanRecord } from '../lib/csv.ts';
import { canModifyThreshold, type UserRole } from '../lib/security.ts';
import { answerShelfQuestion, formatNumberForLocale, type ChatLocale } from '../lib/chat-tools.ts';

// Describes the published detector; written by the training slice, read at runtime.
interface ModelManifest {
  model_file: string;
  run_id: string;
  input_size: number;
  params: DetectorParams;
  sha256: string;
  validation_map50: number;
  validation_max_dets: number;
  preprocessing?: FcosPreprocessing;
  webgpu_capable?: boolean;
}

// Loads an object URL into an image element so its pixels can be drawn to a canvas.
function loadImageElement(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('image could not be decoded'));
    image.src = url;
  });
}

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
  const [modelManifest, setModelManifest] = useState<ModelManifest | null>(null);
  const [modelChecked, setModelChecked] = useState(false);
  const [analysisState, setAnalysisState] = useState<'idle' | 'analysing' | 'done' | 'error'>('idle');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const sessionRef = useRef<{ session: Awaited<ReturnType<typeof loadOnnxDetector>>['session']; provider: 'webgpu' | 'wasm' } | null>(
    null,
  );

  const dict = DICTIONARIES[locale];
  const MODEL_AVAILABLE = Boolean(modelManifest);

  // Ask the deployment whether a model file was published with it.
  useEffect(() => {
    let cancelled = false;
    fetch('/models/manifest.json', { cache: 'no-store' })
      .then((response) => (response.ok ? response.json() : null))
      .then((manifest: ModelManifest | null) => {
        if (cancelled) return;
        setModelManifest(manifest);
        setModelChecked(true);
      })
      .catch(() => {
        if (!cancelled) setModelChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Creates the ONNX session once per page visit and reuses it for every photo.
  const getSession = useCallback(async () => {
    if (sessionRef.current) return sessionRef.current;
    if (!modelManifest) throw new Error('no model manifest published');
    const created = await loadOnnxDetector(modelManifest.model_file, modelManifest.webgpu_capable !== false);
    sessionRef.current = created;
    return created;
  }, [modelManifest]);

  // Draws the photo stretched to a square on a canvas and runs the detector on those pixels.
  const analysePhoto = useCallback(
    async (file: File) => {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
      setAnalysisState('analysing');
      setDetection(null);
      try {
        const image = await loadImageElement(url);
        const params = modelManifest?.params ?? DEFAULT_DETECTOR_PARAMS;
        const preprocessing = modelManifest?.preprocessing ?? MODERN_PREPROCESSING;
        const canvas = document.createElement('canvas');
        canvas.width = params.inputSize;
        canvas.height = params.inputSize;
        const context = canvas.getContext('2d');
        if (!context) throw new Error('canvas is unavailable');
        context.drawImage(image, 0, 0, params.inputSize, params.inputSize);
        const rgba = context.getImageData(0, 0, params.inputSize, params.inputSize).data;
        const ready = await getSession();
        const outcome = await runFcosDetection(
          ready.session as Parameters<typeof runFcosDetection>[0],
          ready.provider,
          rgba,
          image.naturalWidth,
          image.naturalHeight,
          params,
          preprocessing,
        );
        setDetection(
          buildDetectionResult(
            outcome.boxes,
            image.naturalWidth,
            image.naturalHeight,
            threshold,
            outcome.inferenceMs,
            outcome.executionProvider,
          ),
        );
        setAnalysisState('done');
      } catch {
        setAnalysisState('error');
        setErrorMsg(dict.errorModelLoad);
      }
    },
    [dict.errorModelLoad, getSession, modelManifest, threshold],
  );
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
      // Do not fabricate detections when no trained model is published.
      computeResizedDimensions(1280, 720, 1280);
      setDetection(null);
      return;
    }
    void analysePhoto(file);
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

          {modelChecked && !MODEL_AVAILABLE && (
            <div role="status" className="badge-warn" style={{ display: 'block', marginBottom: '0.85rem' }}>
              <strong>{dict.modelMissingTitle}.</strong> {dict.modelMissingBody}
            </div>
          )}

          {analysisState === 'analysing' && (
            <div role="status" className="badge-ok" style={{ display: 'block', marginBottom: '0.85rem' }}>
              <strong>{dict.analysingTitle}…</strong> {dict.analysingBody}
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

          {previewUrl && (
            <div className="canvas-box" style={{ position: 'relative' }}>
              {/* The photo itself stays in this tab; only the boxes are drawn over it. */}
              <img src={previewUrl} alt={dict.overlayLabel} style={{ width: '100%', display: 'block' }} />
            </div>
          )}

          {detection && (
            <div className="canvas-box">
              <svg
                viewBox={`0 0 ${detection.imageWidth} ${detection.imageHeight}`}
                role="img"
                aria-label={dict.overlayLabel}
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
          {detection && (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }} data-testid="inference-info">
              {detection.count} products in {detection.inferenceMs} ms on {detection.executionProvider.toUpperCase()}
            </p>
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
