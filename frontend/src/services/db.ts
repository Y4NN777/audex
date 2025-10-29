import { openDB, type IDBPDatabase } from "idb";

import type { BatchSummary, StoredFile } from "../types/batch";

type BatchRecord = BatchSummary & { syncedAt?: string };
type FileRecord = {
  id: string;
  batchId: string;
  file: File;
};

const DB_NAME = "audex-client";
const DB_VERSION = 1;
const BATCH_STORE = "batches";
const FILES_STORE = "files";

let dbPromise: Promise<IDBPDatabase> | null = null;

async function getDB(): Promise<IDBPDatabase> {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(BATCH_STORE)) {
          db.createObjectStore(BATCH_STORE, { keyPath: "id" });
        }
        if (!db.objectStoreNames.contains(FILES_STORE)) {
          const filesStore = db.createObjectStore(FILES_STORE, { keyPath: "id" });
          filesStore.createIndex("by-batch", "batchId");
        }
      }
    });
  }
  return dbPromise;
}

export async function persistBatch(batch: BatchSummary, files: File[]): Promise<void> {
  const db = await getDB();
  const tx = db.transaction([BATCH_STORE, FILES_STORE], "readwrite");
  await tx.objectStore(BATCH_STORE).put(batch satisfies BatchRecord);

  const fileStore = tx.objectStore(FILES_STORE);
  await Promise.all(
    files.map((file, index) =>
      fileStore.put({
        id: `${batch.id}:${index}`,
        batchId: batch.id,
        file
      } satisfies FileRecord)
    )
  );
  await tx.done;
}

export async function updateBatch(batch: BatchSummary): Promise<void> {
  const db = await getDB();
  await db.put(BATCH_STORE, batch satisfies BatchRecord);
}

export async function deleteBatch(batchId: string): Promise<void> {
  const db = await getDB();
  const tx = db.transaction([BATCH_STORE, FILES_STORE], "readwrite");
  await tx.objectStore(BATCH_STORE).delete(batchId);
  const fileStore = tx.objectStore(FILES_STORE);
  const index = fileStore.index("by-batch");
  let cursor = await index.openCursor(batchId);
  while (cursor) {
    await cursor.delete();
    cursor = await cursor.continue();
  }
  await tx.done;
}

export async function loadBatches(): Promise<BatchSummary[]> {
  const db = await getDB();
  const records = await db.getAll(BATCH_STORE);
  return (records as BatchRecord[]).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function loadFiles(batchId: string): Promise<File[]> {
  const db = await getDB();
  const tx = db.transaction(FILES_STORE, "readonly");
  const index = tx.store.index("by-batch");
  const files: File[] = [];
  let cursor = await index.openCursor(batchId);
  while (cursor) {
    files.push((cursor.value as FileRecord).file);
    cursor = await cursor.continue();
  }
  await tx.done;
  return files;
}

export async function getBatch(batchId: string): Promise<BatchSummary | undefined> {
  const db = await getDB();
  const record = await db.get(BATCH_STORE, batchId);
  return record as BatchRecord | undefined;
}

export async function mergeBatchRecord(batchId: string, partial: Partial<BatchSummary>): Promise<BatchSummary | undefined> {
  const db = await getDB();
  const record = (await db.get(BATCH_STORE, batchId)) as BatchRecord | undefined;
  if (!record) {
    return undefined;
  }
  const updated: BatchRecord = { ...record, ...partial } as BatchRecord;
  await db.put(BATCH_STORE, updated);
  return updated;
}

export function mapFilesMetadata(files: File[]): StoredFile[] {
  return files.map((file, index) => ({
    id: `${index}-${file.name}`,
    name: file.name,
    size: file.size,
    type: file.type,
    lastModified: file.lastModified
  }));
}
