// pre-push hook: every outgoing commit must be authored and committed by the owner,
// carry no trailers or tool names, and go to main (tags are allowed for releases).
import { readFileSync } from 'node:fs';
import { checkCommitMessage, identityProblems } from '../lib/repo-rules.mjs';
import { ownerIdentity, readCommits } from '../lib/git.mjs';

const ZERO = /^0+$/;
const owner = ownerIdentity();
const lines = readFileSync(0, 'utf8').split(/\r?\n/).filter(Boolean);
const failures = [];

for (const line of lines) {
  const [localRef, localSha, remoteRef, remoteSha] = line.split(' ');
  if (remoteRef.startsWith('refs/tags/')) continue;
  if (remoteRef !== 'refs/heads/main') {
    failures.push(`push to ${remoteRef} refused: this repo uses the main branch only`);
    continue;
  }
  if (ZERO.test(localSha)) {
    failures.push(`deleting ${remoteRef} is not allowed`);
    continue;
  }
  // New branch on the remote: check everything not already on origin.
  const range = ZERO.test(remoteSha) ? [localSha, '--not', '--remotes=origin'] : [`${remoteSha}..${localSha}`];
  for (const commit of readCommits(range)) {
    const problems = [...identityProblems(commit, owner), ...checkCommitMessage(commit.message)];
    for (const p of problems) failures.push(`${commit.sha.slice(0, 7)} (${localRef}): ${p}`);
  }
}

if (failures.length) {
  console.error('Push blocked:');
  for (const f of failures) console.error(`  - ${f}`);
  process.exit(1);
}
