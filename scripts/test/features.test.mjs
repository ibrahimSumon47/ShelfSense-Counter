import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
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
