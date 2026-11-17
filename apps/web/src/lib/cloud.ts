// Server-side Cloudinary signed upload helper and Clerk session role resolver.
// Generates SHA-1 upload signatures using Node's built-in `node:crypto` so client-resized
// 320px thumbnails upload directly to Cloudinary without routing multi-megabyte bodies through Vercel.

import { createHash } from 'node:crypto';
import { type SessionUser, type UserRole } from './security.ts';

export interface CloudinarySignParams {
  timestamp: number;
  folder: string;
  publicId?: string;
}

// Computes the exact hex SHA-1 signature required by Cloudinary's `/image/upload` REST API.
export function signCloudinaryUpload(
  params: CloudinarySignParams,
  apiSecret: string,
): string {
  if (!apiSecret.trim()) {
    throw new Error('Missing CLOUDINARY_API_SECRET');
  }
  const entries: Array<[string, string | number]> = [
    ['folder', params.folder],
    ['timestamp', params.timestamp],
  ];
  if (params.publicId) {
    entries.push(['public_id', params.publicId]);
  }
  entries.sort((a, b) => a[0].localeCompare(b[0]));
  const serialized = entries.map(([k, v]) => `${k}=${v}`).join('&');
  return createHash('sha1')
    .update(`${serialized}${apiSecret}`)
    .digest('hex');
}

// Resolves the active session user and role ('owner' | 'staff') from Clerk request headers
// or falls back to the demo store operator when unauthenticated in public preview mode.
export function resolveClerkSessionUser(headers: Headers): SessionUser {
  const clerkUserId = headers.get('x-clerk-user-id') || 'user-owner-1';
  const requestedRole = headers.get('x-shelfsense-role');
  const role: UserRole = requestedRole === 'staff' ? 'staff' : 'owner';
  return {
    userId: clerkUserId,
    role,
    displayName: role === 'owner' ? 'Store Owner' : 'Aisle Staff',
  };
}
