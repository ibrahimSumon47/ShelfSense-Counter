import { NextResponse } from 'next/server';
import { resolveClerkSessionUser, signCloudinaryUpload } from '../../../lib/cloud.ts';
import { NEON_POSTGRES_DDL } from '../../../lib/schema.ts';

export async function GET(request: Request) {
  const user = resolveClerkSessionUser(request.headers);
  const clerkConfigured = Boolean(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY,
  );
  const cloudinaryConfigured = Boolean(
    process.env.CLOUDINARY_CLOUD_NAME &&
      process.env.CLOUDINARY_API_KEY &&
      process.env.CLOUDINARY_API_SECRET,
  );
  const databaseConfigured = Boolean(process.env.DATABASE_URL);

  return NextResponse.json({
    status: 'ok',
    user,
    integrations: {
      clerkConfigured,
      cloudinaryConfigured,
      databaseConfigured,
      schemaTables: ['stores', 'aisles', 'shelves', 'scans'],
      ddlLength: NEON_POSTGRES_DDL.length,
    },
  });
}

export async function POST(request: Request) {
  const secret = process.env.CLOUDINARY_API_SECRET || 'demo_secret';
  const cloudName = process.env.CLOUDINARY_CLOUD_NAME || 'demo_cloud';
  const apiKey = process.env.CLOUDINARY_API_KEY || 'demo_key';
  const timestamp = Math.floor(Date.now() / 1000);
  const folder = 'shelfsense/thumbnails';
  const signature = signCloudinaryUpload({ timestamp, folder }, secret);

  return NextResponse.json({
    cloudName,
    apiKey,
    timestamp,
    folder,
    signature,
  });
}
