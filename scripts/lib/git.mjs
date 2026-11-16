// Small wrappers around the git CLI so hooks and CI scripts read commits the same way.
import { execFileSync } from 'node:child_process';

// Runs git and returns trimmed stdout. Throws with git's own error text on failure.
export function git(args, options = {}) {
  return execFileSync('git', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], ...options }).trimEnd();
}

// The identity the owner has configured globally; every commit must match it.
export function ownerIdentity() {
  return { name: git(['config', 'user.name']), email: git(['config', 'user.email']) };
}

const FIELD = '\x1f';
const RECORD = '\x1e';

// Reads commits for the given rev-list arguments (e.g. ['HEAD'] or ['a..b']).
// Unit and record separators keep multi-line messages intact.
export function readCommits(revArgs) {
  const format = ['%H', '%an', '%ae', '%cn', '%ce', '%B'].join('%x1f') + '%x1e';
  const out = git(['log', `--format=${format}`, ...revArgs]);
  return out
    .split(RECORD)
    .map((r) => r.replace(/^\s+/, ''))
    .filter(Boolean)
    .map((r) => {
      const [sha, authorName, authorEmail, committerName, committerEmail, message] = r.split(FIELD);
      return { sha, authorName, authorEmail, committerName, committerEmail, message: message ?? '' };
    });
}
