import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { featureProblems, summarise } from '../lib/features.mjs';

const root = mkdtempSync(join(tmpdir(), 'features-'));
writeFileSync(join(root, 'proof.md'), 'ok');

const base = { id: 'X-1', phase: 'S0', title: 'Thing', status: 'todo', model: '[MODEL: Some Model, MID]', evidence: [] };

test('a todo item without evidence is valid but open', () => {
  assert.deepEqual(featureProblems(base, root), []);
  const s = summarise([base], root);
  assert.equal(s.open.length, 1);
  assert.equal(s.done, 0);
});

test('done needs evidence', () => {
  const p = featureProblems({ ...base, status: 'done' }, root);
  assert.ok(p.some((x) => x.includes('without evidence')));
});

test('file evidence must exist', () => {
  assert.deepEqual(featureProblems({ ...base, status: 'done', evidence: ['file:proof.md'] }, root), []);
  const p = featureProblems({ ...base, status: 'done', evidence: ['file:missing.md'] }, root);
  assert.ok(p.some((x) => x.includes('not found')));
});

test('free-text evidence is accepted for done items', () => {
  assert.deepEqual(featureProblems({ ...base, status: 'done', evidence: ['ci: run 123 green'] }, root), []);
});

test('model tag format is enforced', () => {
  assert.ok(featureProblems({ ...base, model: 'Opus high' }, root).length);
  assert.ok(featureProblems({ ...base, model: '[MODEL: Opus, ULTRA]' }, root).length);
});

test('unknown status and duplicate ids are reported', () => {
  assert.ok(featureProblems({ ...base, status: 'finished' }, root).length);
  const s = summarise([base, base], root);
  assert.ok(s.problems.some((x) => x.includes('duplicate')));
});

test('all done means nothing open', () => {
  const s = summarise([{ ...base, status: 'done', evidence: ['file:proof.md'] }], root);
  assert.equal(s.open.length, 0);
  assert.equal(s.problems.length, 0);
});

test('metric features reject simulate_* functions or missing command/run_id in reports', () => {
  writeFileSync(join(root, 'bad-sim.md'), 'Command: python train.py\nrun_id: r1\nUses simulate_predictions for mAP.');
  writeFileSync(join(root, 'good-real.md'), 'Command: python training/train.py\nRun ID: improved-fcos-r50-fpn-v2\nmAP50: 0.61');

  const simEntry = {
    ...base,
    id: 'S3-01',
    status: 'done',
    evidence: ['report:bad-sim.md'],
  };
  const simProblems = featureProblems(simEntry, root);
  assert.ok(simProblems.some((x) => x.includes('simulate_')));

  const goodEntry = {
    ...base,
    id: 'S3-01',
    status: 'done',
    evidence: ['report:good-real.md'],
  };
  assert.deepEqual(featureProblems(goodEntry, root), []);

  // Guard: training/train.py must never define or call any function starting with simulate_.
  const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
  const trainPy = readFileSync(join(repoRoot, 'training/train.py'), 'utf8');
  assert.equal(/\bsimulate_[a-zA-Z0-9_]*\b/.test(trainPy), false, 'training/train.py must not contain simulate_*');
});

