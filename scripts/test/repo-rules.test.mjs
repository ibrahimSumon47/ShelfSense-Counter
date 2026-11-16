import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  checkCommitMessage,
  cleanMessage,
  findBannedText,
  findTrailers,
  forbiddenPathReason,
  identityProblems,
  scanFileText,
} from '../lib/repo-rules.mjs';

test('plain messages pass', () => {
  assert.deepEqual(checkCommitMessage('Add shelf gap detection\n\nUses median spacing between boxes.'), []);
  assert.deepEqual(checkCommitMessage('fix: typo in the README'), []);
});

test('co-author trailer is blocked', () => {
  const problems = checkCommitMessage('Add thing\n\nCo-authored-by: Someone <a@b.c>');
  assert.ok(problems.some((p) => p.toLowerCase().includes('banned text: "co-authored-by"')));
  assert.ok(problems.some((p) => p.includes('trailer')));
});

test('any trailer in the last paragraph is blocked', () => {
  assert.deepEqual(findTrailers('Add thing\n\nSigned-off-by: Me <me@x.y>'), ['Signed-off-by: Me <me@x.y>']);
  assert.deepEqual(findTrailers('Subject only: with a colon'), []);
});

test('tool and bot names are blocked case-insensitively', () => {
  assert.deepEqual(findBannedText('Built with Claude'), ['claude']);
  assert.deepEqual(findBannedText('ANTIGRAVITY session'), ['antigravity']);
  assert.ok(findBannedText('Generated with some tool').length);
  assert.ok(findBannedText('dependabot[bot] bump').includes('dependabot'));
  assert.ok(findBannedText('merge from github-actions').includes('github-actions'));
});

test('names inside other words are not flagged', () => {
  assert.deepEqual(findBannedText('decoder codexample'), []);
  assert.deepEqual(findBannedText('the cursor moved'), []);
});

test('comments and scissors are removed before checking', () => {
  const raw = 'Real subject\n# Please enter the message, claude\n# ------------------------ >8 ------------------------\ndiff text claude';
  assert.equal(cleanMessage(raw), 'Real subject');
  assert.deepEqual(checkCommitMessage(raw), []);
});

test('empty message is rejected', () => {
  assert.deepEqual(checkCommitMessage('# only a comment\n'), ['empty commit message']);
});

test('forbidden paths are recognised', () => {
  assert.equal(forbiddenPathReason('.env'), 'env file');
  assert.equal(forbiddenPathReason('apps/web/.env.local'), 'env file');
  assert.equal(forbiddenPathReason('apps/web/.env.example'), null);
  assert.equal(forbiddenPathReason('private/OWNER_ANSWERS.md'), 'private notes');
  assert.equal(forbiddenPathReason('training/best.onnx'), 'model weights');
  assert.equal(forbiddenPathReason('data/sku110k/img.jpg'), 'dataset folder');
  assert.equal(forbiddenPathReason('.github/dependabot.yml'), 'dependency bot config');
  assert.equal(forbiddenPathReason('renovate.json'), 'dependency bot config');
  assert.equal(forbiddenPathReason('.gemini/settings.json'), 'local assistant state');
  assert.equal(forbiddenPathReason('kaggle.json'), 'kaggle credentials');
  assert.equal(forbiddenPathReason('apps/web/src/app/page.tsx'), null);
});

test('README is scanned fully, code only at the top, other docs not at all', () => {
  assert.deepEqual(scanFileText('README.md', 'Intro\n'.repeat(50) + 'made with gemini'), ['gemini']);
  assert.deepEqual(scanFileText('src/a.ts', '// header by claude\nexport {}'), ['claude']);
  assert.deepEqual(scanFileText('src/a.ts', 'x\n'.repeat(20) + 'const model = "gemini-flash";'), []);
  assert.deepEqual(scanFileText('docs/features.json', '[MODEL: Claude Opus, HIGH]'), []);
  assert.deepEqual(scanFileText('scripts/lib/repo-rules.mjs', 'claude'), []);
});

test('identity must match the owner exactly', () => {
  const owner = { name: 'Owner Name', email: 'owner@example.com' };
  const ok = { authorName: 'Owner Name', authorEmail: 'OWNER@example.com', committerName: 'Owner Name', committerEmail: 'owner@example.com' };
  assert.deepEqual(identityProblems(ok, owner), []);
  const bad = { ...ok, authorName: 'Bot', authorEmail: 'bot@example.com' };
  assert.equal(identityProblems(bad, owner).length, 1);
});
