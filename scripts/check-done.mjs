// Exits non-zero until every feature in docs/features.json is done with evidence.
// Prints the first open item and the model tag to use for it, so a new session
// knows exactly where to resume. With --validate (used in CI) it only fails on
// malformed entries, because open items are normal while the project is in progress.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { summarise } from './lib/features.mjs';

const args = process.argv.slice(2);
const validateOnly = args.includes('--validate');
const fileArg = args.find((a) => !a.startsWith('--'));
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const file = fileArg ? resolve(fileArg) : resolve(root, 'docs/features.json');
const { features } = JSON.parse(readFileSync(file, 'utf8'));
const { problems, open, done, total } = summarise(features, root);

console.log(`Features done: ${done}/${total}`);
if (problems.length) {
  console.error('Problems in features.json:');
  for (const p of problems) console.error(`  - ${p}`);
}
if (open.length) {
  const next = open.find((f) => f.status === 'in_progress') ?? open.find((f) => f.status !== 'blocked') ?? open[0];
  console.log(`Next: ${next.id} ${next.title} (${next.status})`);
  console.log(`Use:  ${next.model}`);
  const blocked = open.filter((f) => f.status === 'blocked').map((f) => f.id);
  if (blocked.length) console.log(`Blocked: ${blocked.join(', ')}`);
}
process.exit(problems.length || (open.length && !validateOnly) ? 1 : 0);
