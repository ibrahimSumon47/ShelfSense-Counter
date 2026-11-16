// commit-msg hook: rejects co-author trailers, any trailer, and tool or bot names.
import { readFileSync } from 'node:fs';
import { checkCommitMessage } from '../lib/repo-rules.mjs';

const file = process.argv[2];
if (!file) {
  console.error('commit-msg: no message file given');
  process.exit(1);
}

const problems = checkCommitMessage(readFileSync(file, 'utf8'));
if (problems.length) {
  console.error('Commit blocked:');
  for (const p of problems) console.error(`  - ${p}`);
  console.error('Rewrite the message in plain words, with no trailers.');
  process.exit(1);
}
