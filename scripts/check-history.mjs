// CI history check: every commit on main must belong to the owner's GitHub account,
// carry no trailers or tool names, and main must be the only branch.
// Locally (no GITHUB_REPOSITORY) it compares against the global git identity instead.
import { execFileSync } from 'node:child_process';
import { checkCommitMessage, identityProblems } from './lib/repo-rules.mjs';
import { ownerIdentity, readCommits } from './lib/git.mjs';

const OWNER_LOGIN = process.env.OWNER_LOGIN || 'ibrahimSumon47';
const repo = process.env.GITHUB_REPOSITORY;

// Calls the GitHub CLI (preinstalled on Actions runners, authenticated by GH_TOKEN).
function gh(args) {
  return execFileSync('gh', args, { encoding: 'utf8' }).trim();
}

const failures = [];
const commits = readCommits(['HEAD']);

for (const commit of commits) {
  for (const p of checkCommitMessage(commit.message)) failures.push(`${commit.sha.slice(0, 7)}: ${p}`);
}

if (repo) {
  // GitHub resolves each commit email to an account; that is what the contributors list shows.
  const head = process.env.GITHUB_SHA || 'HEAD';
  const rows = gh(['api', '--paginate', `repos/${repo}/commits?sha=${head}&per_page=100`, '--jq',
    '.[] | [.sha, (.author.login // "none"), (.committer.login // "none")] | @tsv']);
  for (const row of rows.split('\n').filter(Boolean)) {
    const [sha, author, committer] = row.split('\t');
    if (author !== OWNER_LOGIN) failures.push(`${sha.slice(0, 7)}: author account is ${author}`);
    // web-flow is GitHub itself when the owner edits a file in the browser.
    if (committer !== OWNER_LOGIN && committer !== 'web-flow') {
      failures.push(`${sha.slice(0, 7)}: committer account is ${committer}`);
    }
  }
  const branches = gh(['api', `repos/${repo}/branches`, '--jq', '.[].name']).split('\n').filter(Boolean);
  for (const b of branches) if (b !== 'main') failures.push(`extra branch on GitHub: ${b}`);
} else {
  const owner = ownerIdentity();
  for (const commit of commits) {
    for (const p of identityProblems(commit, owner)) failures.push(`${commit.sha.slice(0, 7)}: ${p}`);
  }
}

if (failures.length) {
  console.error('History check failed:');
  for (const f of failures) console.error(`  - ${f}`);
  process.exit(1);
}
console.log(`History check passed (${commits.length} commits).`);
