// Rules for docs/features.json. Kept separate from the CLI so they can be unit tested.
import { existsSync } from 'node:fs';
import { join } from 'node:path';

export const STATUSES = ['todo', 'in_progress', 'blocked', 'done'];
const MODEL_TAG = /^\[MODEL: [^,\]]+, (LOW|MID|HIGH)\]$/;

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
    for (const item of evidence) {
      const m = /^(file|report):(.+)$/.exec(item);
      if (m && !existsSync(join(root, m[2].trim()))) problems.push(`${id}: evidence file not found: ${m[2].trim()}`);
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
