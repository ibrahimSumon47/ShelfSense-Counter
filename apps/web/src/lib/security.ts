// Upload validation, magic-byte inspection, per-user sliding-window rate limiter,
// and role-based access control (owner vs staff).

export type UserRole = 'owner' | 'staff';

export interface SessionUser {
  userId: string;
  role: UserRole;
  displayName: string;
}

const MAX_THUMBNAIL_BYTES = 1024 * 1024; // 1 MB max for client-resized thumbnail uploads
const ALLOWED_MIME_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp']);

// Inspects the first 12 magic bytes of an image buffer to verify it is genuinely JPEG, PNG, or WebP.
export function detectImageMimeFromBytes(bytes: Uint8Array): string | null {
  if (bytes.length < 12) return null;
  // JPEG: FF D8 FF
  if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
    return 'image/jpeg';
  }
  // PNG: 89 50 4E 47 0D 0A 1A 0A
  if (
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47 &&
    bytes[4] === 0x0d &&
    bytes[5] === 0x0a &&
    bytes[6] === 0x1a &&
    bytes[7] === 0x0a
  ) {
    return 'image/png';
  }
  // WebP: "RIFF" .... "WEBP"
  if (
    bytes[0] === 0x52 &&
    bytes[1] === 0x49 &&
    bytes[2] === 0x46 &&
    bytes[3] === 0x46 &&
    bytes[8] === 0x57 &&
    bytes[9] === 0x45 &&
    bytes[10] === 0x42 &&
    bytes[11] === 0x50
  ) {
    return 'image/webp';
  }
  return null;
}

export interface UploadValidationResult {
  valid: boolean;
  reason?: string;
  detectedMime?: string;
}

// Validates file size, declared MIME type, and actual magic bytes.
export function validateImageUpload(
  bytes: Uint8Array,
  declaredMime: string,
  maxBytes = MAX_THUMBNAIL_BYTES,
): UploadValidationResult {
  if (bytes.length === 0) {
    return { valid: false, reason: 'Empty file upload.' };
  }
  if (bytes.length > maxBytes) {
    return { valid: false, reason: `File exceeds the ${(maxBytes / 1024).toFixed(0)} KB limit.` };
  }
  const normalizedDeclared = declaredMime.trim().toLowerCase();
  if (!ALLOWED_MIME_TYPES.has(normalizedDeclared)) {
    return { valid: false, reason: `Unsupported MIME type: ${declaredMime}.` };
  }
  const magicMime = detectImageMimeFromBytes(bytes);
  if (!magicMime || magicMime !== normalizedDeclared) {
    return { valid: false, reason: 'File header bytes do not match the declared image format.' };
  }
  return { valid: true, detectedMime: magicMime };
}

// Checks whether a user role is permitted to update low-stock thresholds.
// Per owner intake: staff can scan shelves, but only the owner can modify thresholds.
export function canModifyThreshold(user: SessionUser): boolean {
  return user.role === 'owner';
}

// Filters any collection of user-owned records so a user can never read or mutate another user's data.
export function filterByUser<T extends { userId: string }>(records: readonly T[], userId: string): T[] {
  if (!userId.trim()) return [];
  return records.filter((rec) => rec.userId === userId);
}

// Sliding-window rate limiter keyed by userId or IP address.
export class SlidingWindowRateLimiter {
  private readonly maxRequests: number;
  private readonly windowMs: number;
  private readonly hits = new Map<string, number[]>();

  constructor(maxRequests = 20, windowMs = 60_000) {
    this.maxRequests = maxRequests;
    this.windowMs = windowMs;
  }

  // Returns { allowed, remaining, retryAfterMs } for the given key at timestamp `nowMs`.
  check(key: string, nowMs = Date.now()): { allowed: boolean; remaining: number; retryAfterMs: number } {
    const cutoff = nowMs - this.windowMs;
    const prev = (this.hits.get(key) ?? []).filter((t) => t > cutoff);
    if (prev.length >= this.maxRequests) {
      const oldest = prev[0];
      return {
        allowed: false,
        remaining: 0,
        retryAfterMs: Math.max(0, oldest + this.windowMs - nowMs),
      };
    }
    prev.push(nowMs);
    this.hits.set(key, prev);
    return {
      allowed: true,
      remaining: Math.max(0, this.maxRequests - prev.length),
      retryAfterMs: 0,
    };
  }
}
