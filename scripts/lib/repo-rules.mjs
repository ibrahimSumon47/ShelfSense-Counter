// Shared repository rules. The git hooks and the CI checks import this one file
// so a commit that passes locally cannot fail in CI for a different reason.

// Tool, assistant and bot names that must never appear in commit messages,
// file headers or the README. Matched as whole words, case-insensitive.
export const BANNED_NAMES = [
  'antigravity',
  'gemini',
  'claude',
  'codebuff',
  'anthropic',
  'openai',
  'chatgpt',
  'copilot',
  'codex',
  'devin',
  'aider',
  'windsurf',
  'codeium',
  'tabnine',
  'dependabot',
  'renovate',
  'github-actions',
];

// Phrases that signal machine authorship or a co-author, whatever the name.
export const BANNED_PHRASES = [
  /co-authored-by/i,
  /generated (with|by)/i,
  /\[bot\]/i,
  /\bai[- ]generated\b/i,
  /\bwritten by (an )?ai\b/i,
];

// Paths that must never be tracked. Each entry explains itself by name.
const FORBIDDEN_PATH_RULES = [
  { why: 'env file', re: /(^|\/)\.env(\.(?!example$)[^/]*)?$/ },
  { why: 'private notes', re: /^private\// },
  { why: 'kaggle credentials', re: /(^|\/)(kaggle\.json|access_token)$/ },
  { why: 'key material', re: /\.(pem|key|p12|pfx)$/i },
  { why: 'dataset folder', re: /^(data|datasets|training\/data|uploads|raw_uploads)\// },
  { why: 'model weights', re: /\.(pt|pth|ckpt|safetensors|onnx|ort|tflite|h5|npz)$/i },
  { why: 'archive', re: /\.(zip|tar|tar\.gz|7z)$/i },
  { why: 'local assistant state', re: /^\.(agent|agents|antigravity|gemini|claude|codebuff|cursor|windsurf|continue|history)\// },
  { why: 'dependency bot config', re: /^\.github\/dependabot\.ya?ml$|(^|\/)(renovate\.json5?|\.renovaterc(\.json)?)$/ },
];

// Files allowed to mention the banned names because they define or test them.
export const HEADER_SCAN_EXEMPT = new Set([
  'scripts/lib/repo-rules.mjs',
  'scripts/test/repo-rules.test.mjs',
]);

const CODE_EXTENSIONS = /\.(m?js|cjs|ts|tsx|jsx|py|css|scss|sh|ya?ml|toml|sql)$/i;
const HEADER_LINES = 15;

function escapeRegex(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const NAME_PATTERNS = BANNED_NAMES.map((name) => ({
  name,
  // Lookarounds instead of \b so names containing '-' still match as one word.
  re: new RegExp(`(?<![a-z0-9])${escapeRegex(name)}(?![a-z0-9])`, 'i'),
}));

// Returns every banned name or phrase found in the text (empty array = clean).
export function findBannedText(text) {
  const hits = [];
  for (const { name, re } of NAME_PATTERNS) if (re.test(text)) hits.push(name);
  for (const re of BANNED_PHRASES) {
    const m = text.match(re);
    if (m) hits.push(m[0]);
  }
  return hits;
}

// Drops git comment lines and anything below the scissors line, the same
// cleanup git applies before storing the message.
export function cleanMessage(raw) {
  const cut = raw.split(/^# -+ >8 -+$/m)[0];
  return cut
    .split(/\r?\n/)
    .filter((line) => !line.startsWith('#'))
    .join('\n')
    .trim();
}

// Finds git-style trailers ("Key: value" lines in the final paragraph).
// The subject paragraph is never treated as trailers, so "fix: typo" is fine.
export function findTrailers(message) {
  const paragraphs = cleanMessage(message)
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);
  if (paragraphs.length < 2) return [];
  const last = paragraphs[paragraphs.length - 1].split('\n');
  return last.filter((line) => /^[A-Za-z][A-Za-z0-9-]*:\s+\S/.test(line));
}

// Full commit message check used by commit-msg, pre-push and CI.
export function checkCommitMessage(raw) {
  const problems = [];
  const message = cleanMessage(raw);
  if (!message) problems.push('empty commit message');
  for (const hit of findBannedText(message)) problems.push(`banned text: "${hit}"`);
  for (const t of findTrailers(message)) problems.push(`trailer not allowed: "${t}"`);
  return problems;
}

// Returns the reason a path must not be tracked, or null if it is fine.
export function forbiddenPathReason(path) {
  const normalised = path.replace(/\\/g, '/');
  for (const rule of FORBIDDEN_PATH_RULES) if (rule.re.test(normalised)) return rule.why;
  return null;
}

// Checks the top of a source file (or the whole README) for banned names.
export function scanFileText(path, text) {
  const normalised = path.replace(/\\/g, '/');
  if (HEADER_SCAN_EXEMPT.has(normalised)) return [];
  if (/^readme\.md$/i.test(normalised)) return findBannedText(text);
  if (!CODE_EXTENSIONS.test(normalised)) return [];
  const header = text.split(/\r?\n/).slice(0, HEADER_LINES).join('\n');
  return findBannedText(header);
}

// Compares a commit's author and committer with the owner's identity.
export function identityProblems(commit, owner) {
  const problems = [];
  const same = (a, b) => a.trim().toLowerCase() === b.trim().toLowerCase();
  if (!same(commit.authorEmail, owner.email) || commit.authorName.trim() !== owner.name.trim()) {
    problems.push(`author is ${commit.authorName} <${commit.authorEmail}>`);
  }
  if (!same(commit.committerEmail, owner.email) || commit.committerName.trim() !== owner.name.trim()) {
    problems.push(`committer is ${commit.committerName} <${commit.committerEmail}>`);
  }
  return problems;
}
