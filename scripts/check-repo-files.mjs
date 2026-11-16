// Tracked-file check: no secrets, datasets, weights or bot configs in git, nothing
// over the size cap, and no tool names in the README or source file headers.
import { readFileSync, statSync } from 'node:fs';
import { forbiddenPathReason, scanFileText } from './lib/repo-rules.mjs';
import { git } from './lib/git.mjs';

// Anything larger is almost certainly data or weights that belong in a Release.
const MAX_BYTES = 2 * 1024 * 1024;
const TEXT_FILE = /\.(md|m?js|cjs|ts|tsx|jsx|py|css|scss|sh|ya?ml|toml|sql|json)$/i;

const files = git(['ls-files', '-z']).split('\0').filter(Boolean);
const failures = [];

for (const path of files) {
  const why = forbiddenPathReason(path);
  if (why) failures.push(`${path}: ${why} must not be tracked`);

  let size = 0;
  try {
    size = statSync(path).size;
  } catch {
    continue; // deleted in the working tree but still in the index
  }
  if (size > MAX_BYTES) failures.push(`${path}: ${(size / 1048576).toFixed(1)} MB is over the 2 MB cap`);

  if (TEXT_FILE.test(path) || /^readme\.md$/i.test(path)) {
    const hits = scanFileText(path, readFileSync(path, 'utf8'));
    if (hits.length) failures.push(`${path}: mentions ${hits.join(', ')}`);
  }
}

if (failures.length) {
  console.error('Repository file check failed:');
  for (const f of failures) console.error(`  - ${f}`);
  process.exit(1);
}
console.log(`Repository file check passed (${files.length} files).`);
