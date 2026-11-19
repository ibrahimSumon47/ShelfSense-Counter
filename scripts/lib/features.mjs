// Rules for docs/features.json. Kept separate from the CLI so they can be unit tested.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

export const STATUSES = ['todo', 'in_progress', 'blocked', 'done'];
const MODEL_TAG = /^\[MODEL: [^,\]]+, (LOW|MID|HIGH)\]$/;

// Features that report model/evaluation metrics and must cite a report containing
// the exact command, run id, and real (non-simulated) model predictions.
export const METRIC_FEATURE_IDS = new Set([
  'S2-03',
  'S2-04',
  'S2-05',
  'S2-06',
  'S3-01',
  'S3-02',
  'S5-03',
]);

// Features whose numbers must come from model predictions, so their report has to name the
// exact command, the Kaggle kernel version that produced the weights, and a committed
// prediction file anyone can rescore. S5-03 (chat) is a live-LLM evaluation, not a detector
// measurement, so it only needs a command and an identifier.
export const MODEL_METRIC_FEATURE_IDS = new Set(['S2-03', 'S2-04', 'S2-05', 'S2-06', 'S3-01', 'S3-02']);

// Verifies that a metric report file contains a command, a run_id, and does not
// come from any `simulate_*` function or unmeasured placeholder.
export function metricReportProblems(id, reportPath, text) {
  const problems = [];
  if (/not measured yet/i.test(text)) {
    problems.push(`${id}: report ${reportPath} still says "not measured yet"`);
  }
  if (/\bsimulate_[a-z0-9_]*\b/i.test(text)) {
    problems.push(`${id}: report ${reportPath} references a simulate_* function`);
  }
  if (!/\b(Command|command)\b/.test(text)) {
    problems.push(`${id}: report ${reportPath} is missing the exact command that produced it`);
  }
  if (!/\b(run_id|Run ID|Model|model)\b/.test(text)) {
    problems.push(`${id}: report ${reportPath} is missing the run_id or model identifier`);
  }
  if (MODEL_METRIC_FEATURE_IDS.has(id)) {
    if (!/\bkernel\b[\s\S]{0,80}?\bversion\b|\bkernel version\b/i.test(text)) {
      problems.push(`${id}: report ${reportPath} must name the Kaggle kernel version that produced the weights`);
    }
    if (!/predictions\/[\w./-]+\.json(\.gz)?/i.test(text)) {
      problems.push(`${id}: report ${reportPath} must point at a committed prediction file (predictions/*.json(.gz))`);
    }
  }
  return problems;
}

// Returns a list of structural problems with one feature entry.
// `root` is where file: and report: evidence paths are resolved.
export function featureProblems(feature, root) {
  const problems = [];
  const id = feature.id ?? '(no id)';
  for (const key of ['id', 'phase', 'title', 'status', 'model']) {
    if (typeof feature[key] !== 'string' || !feature[key].trim()) problems.push(`${id}: missing ${key}`);
  }
  if (feature.status && !STATUSES.includes(feature.status)) problems.push(`${id}: unknown status ${feature.status}`);
  if (feature.model && !MODEL_TAG.test(feature.model)) problems.push(`${id}: model tag must look like [MODEL: Name, MID]`);
  if (!Array.isArray(feature.evidence)) problems.push(`${id}: evidence must be an array`);

  // A done item needs evidence, and any file it points to must really exist.
  if (feature.status === 'done') {
    const evidence = Array.isArray(feature.evidence) ? feature.evidence : [];
    if (!evidence.length) problems.push(`${id}: marked done without evidence`);
    let hasReport = false;
    for (const item of evidence) {
      if (/\bnot measured yet\b/i.test(item) || /\bsimulate_[a-z0-9_]*\b/i.test(item)) {
        problems.push(`${id}: done feature cannot use unmeasured or simulated evidence: ${item}`);
      }
      const m = /^(file|report):(.+)$/.exec(item);
      if (m) {
        const rel = m[2].trim();
        const full = join(root, rel);
        if (!existsSync(full)) {
          problems.push(`${id}: evidence file not found: ${rel}`);
        } else if (m[1] === 'report') {
          hasReport = true;
          if (METRIC_FEATURE_IDS.has(id)) {
            problems.push(...metricReportProblems(id, rel, readFileSync(full, 'utf8')));
          }
        }
      }
    }
    if (METRIC_FEATURE_IDS.has(id) && !hasReport) {
      problems.push(`${id}: metric feature must include a report:<path> evidence entry`);
    }
  }
  return problems;
}

// Summarises the whole list: structural problems, open items and duplicates.
export function summarise(features, root) {
  const problems = [];
  const seen = new Set();
  for (const f of features) {
    if (seen.has(f.id)) problems.push(`${f.id}: duplicate id`);
    seen.add(f.id);
    problems.push(...featureProblems(f, root));
  }
  const open = features.filter((f) => f.status !== 'done');
  return { problems, open, done: features.length - open.length, total: features.length };
}
