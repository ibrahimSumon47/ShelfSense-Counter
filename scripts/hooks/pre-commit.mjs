// pre-commit hook: refuses staged secrets, datasets and weights, then runs gitleaks
// on the staged changes. Both checks must pass; there is no skip switch on purpose.
import { execFileSync, spawnSync } from 'node:child_process';
import { forbiddenPathReason } from '../lib/repo-rules.mjs';

const staged = execFileSync('git', ['diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z'], {
  encoding: 'utf8',
})
  .split('\0')
  .filter(Boolean);

const blocked = staged
  .map((path) => ({ path, why: forbiddenPathReason(path) }))
  .filter((item) => item.why);

if (blocked.length) {
  console.error('Commit blocked, these files must not be tracked:');
  for (const { path, why } of blocked) console.error(`  - ${path} (${why})`);
  process.exit(1);
}

// gitleaks scans only what is staged, so it stays fast on large repos.
// No shell: spawnSync finds gitleaks(.exe) on PATH by itself on every platform.
const leaks = spawnSync('gitleaks', ['git', '--pre-commit', '--staged', '--redact', '--no-banner'], {
  stdio: 'inherit',
});
if (leaks.error || leaks.status === null) {
  console.error('gitleaks is not installed or could not start. Install it (winget install Gitleaks.Gitleaks).');
  process.exit(1);
}
if (leaks.status !== 0) {
  console.error('gitleaks found a possible secret in the staged changes. Commit blocked.');
  process.exit(1);
}
