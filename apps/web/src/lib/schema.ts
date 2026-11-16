// Neon Postgres relational schema definitions (Store -> Aisle -> Shelf -> Scan + Threshold).
// Every table carries `ownerUserId` so queries are strictly isolated per account.

export interface StoreEntity {
  id: string;
  ownerUserId: string;
  name: string;
  location: string;
  createdAt: string;
}

export interface AisleEntity {
  id: string;
  storeId: string;
  ownerUserId: string;
  name: string;
}

export interface ShelfEntity {
  id: string;
  aisleId: string;
  storeId: string;
  ownerUserId: string;
  name: string;
  lowStockThreshold: number;
  updatedByRole: 'owner';
}

// SQL DDL migration used for Neon Postgres provisioning (`stores`, `aisles`, `shelves`, `scans`).
export const NEON_POSTGRES_DDL = `
CREATE TABLE IF NOT EXISTS stores (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  location TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS aisles (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
  owner_user_id TEXT NOT NULL,
  name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shelves (
  id TEXT PRIMARY KEY,
  aisle_id TEXT NOT NULL REFERENCES aisles(id) ON DELETE CASCADE,
  store_id TEXT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
  owner_user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  low_stock_threshold INTEGER NOT NULL DEFAULT 15 CHECK (low_stock_threshold >= 1)
);

CREATE TABLE IF NOT EXISTS scans (
  id TEXT PRIMARY KEY,
  shelf_id TEXT NOT NULL REFERENCES shelves(id) ON DELETE CASCADE,
  store_id TEXT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
  owner_user_id TEXT NOT NULL,
  scanned_by_role TEXT NOT NULL CHECK (scanned_by_role IN ('owner', 'staff')),
  scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  item_count INTEGER NOT NULL CHECK (item_count >= 0),
  gap_count INTEGER NOT NULL CHECK (gap_count >= 0),
  estimated_missing INTEGER NOT NULL DEFAULT 0,
  low_stock_threshold INTEGER NOT NULL,
  low_stock BOOLEAN NOT NULL,
  thumbnail_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_scans_owner_date ON scans(owner_user_id, scanned_at DESC);
`.trim();
