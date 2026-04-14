"use client";

import { useCallback, useRef, useState } from "react";
import BottomSheet from "@/components/ui/BottomSheet";
import { uploadDocument } from "@/lib/api";

const ACCEPTED_MIME = ["image/jpeg", "image/png", "application/pdf"];
const ACCEPTED_EXT = ".jpg,.jpeg,.png,.pdf";
const MAX_MB = 10;

type FileStatus = "pending" | "uploading" | "success" | "error";

interface FileEntry {
  id: string;
  file: File;
  status: FileStatus;
  error?: string;
}

interface DocumentUploadModalProps {
  open: boolean;
  token: string;
  onClose: () => void;
}

let _idCounter = 0;
function nextId() {
  _idCounter += 1;
  return String(_idCounter);
}

export default function DocumentUploadModal({ open, token, onClose }: DocumentUploadModalProps) {
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const updateEntry = (id: string, patch: Partial<FileEntry>) =>
    setEntries((prev) => prev.map((e) => (e.id === id ? { ...e, ...patch } : e)));

  const uploadFile = useCallback(
    async (entry: FileEntry) => {
      updateEntry(entry.id, { status: "uploading" });
      try {
        await uploadDocument(token, entry.file);
        updateEntry(entry.id, { status: "success" });
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        updateEntry(entry.id, { status: "error", error: msg });
      }
    },
    [token]
  );

  const addFiles = useCallback(
    (files: FileList | File[]) => {
      const arr = Array.from(files);
      const newEntries: FileEntry[] = [];

      for (const file of arr) {
        if (!ACCEPTED_MIME.includes(file.type)) {
          newEntries.push({
            id: nextId(),
            file,
            status: "error",
            error: "Only JPEG, PNG, and PDF files are accepted.",
          });
          continue;
        }
        if (file.size > MAX_MB * 1024 * 1024) {
          newEntries.push({
            id: nextId(),
            file,
            status: "error",
            error: `File exceeds ${MAX_MB}MB limit.`,
          });
          continue;
        }
        newEntries.push({ id: nextId(), file, status: "pending" });
      }

      setEntries((prev) => [...prev, ...newEntries]);

      // Start uploading valid files immediately
      for (const entry of newEntries) {
        if (entry.status === "pending") {
          uploadFile(entry);
        }
      }
    },
    [uploadFile]
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) {
      addFiles(e.target.files);
      // Reset input so the same file can be re-selected after removal
      e.target.value = "";
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) {
      addFiles(e.dataTransfer.files);
    }
  };

  const handleClose = () => {
    setEntries([]);
    onClose();
  };

  const anyUploading = entries.some((e) => e.status === "uploading" || e.status === "pending");
  const anySuccess = entries.some((e) => e.status === "success");

  const statusIcon = (status: FileStatus) => {
    if (status === "uploading" || status === "pending") return "⏳";
    if (status === "success") return "✅";
    return "❌";
  };

  return (
    <BottomSheet open={open} onClose={handleClose} title="Upload Documents">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `2px dashed ${dragOver ? "#E07D41" : "var(--border, #e0e0e0)"}`,
          borderRadius: 14,
          padding: "24px 16px",
          textAlign: "center",
          cursor: "pointer",
          background: dragOver ? "#FFF5EE" : "var(--bg-app, #f8f8f8)",
          transition: "border-color 0.15s, background 0.15s",
          marginBottom: 16,
        }}
      >
        <div style={{ fontSize: 32, marginBottom: 8 }}>📄</div>
        <div style={{ fontSize: 14, fontWeight: 700, color: "var(--t1, #000)", marginBottom: 4 }}>
          Tap to choose files
        </div>
        <div style={{ fontSize: 12, color: "var(--t3, #999)" }}>
          or drag and drop here
        </div>
        <div style={{ fontSize: 11, color: "var(--t3, #999)", marginTop: 6 }}>
          JPEG, PNG, PDF · Max {MAX_MB}MB each
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXT}
          multiple
          style={{ display: "none" }}
          onChange={handleInputChange}
        />
      </div>

      {/* File list */}
      {entries.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          {entries.map((entry) => (
            <div
              key={entry.id}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 10,
                padding: "10px 12px",
                borderRadius: 10,
                background: "var(--white, #fff)",
                border: "1px solid var(--border, #e0e0e0)",
                marginBottom: 8,
              }}
            >
              <span style={{ fontSize: 18, flexShrink: 0, marginTop: 1 }}>
                {statusIcon(entry.status)}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: "var(--t1, #000)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {entry.file.name}
                </div>
                {entry.status === "uploading" && (
                  <div style={{ fontSize: 11, color: "var(--t3, #999)", marginTop: 2 }}>
                    Uploading…
                  </div>
                )}
                {entry.status === "success" && (
                  <div style={{ fontSize: 11, color: "#2e7d32", marginTop: 2 }}>
                    Uploaded — processing in the background
                  </div>
                )}
                {entry.status === "error" && (
                  <div style={{ fontSize: 11, color: "var(--red, #d32f2f)", marginTop: 2 }}>
                    {entry.error}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Processing note */}
      {anySuccess && !anyUploading && (
        <div
          style={{
            fontSize: 12,
            color: "var(--t2, #555)",
            background: "#FFF5EE",
            borderRadius: 10,
            padding: "10px 12px",
            marginBottom: 16,
            lineHeight: 1.5,
          }}
        >
          Your documents are being processed. Health records will update within a minute.
        </div>
      )}

      {/* Actions */}
      <button
        type="button"
        onClick={handleClose}
        disabled={anyUploading}
        style={{
          width: "100%",
          padding: "12px 16px",
          borderRadius: 10,
          border: "none",
          background: anyUploading ? "var(--border, #e0e0e0)" : "#E07D41",
          color: anyUploading ? "var(--t3, #999)" : "white",
          fontSize: 14,
          fontWeight: 700,
          cursor: anyUploading ? "default" : "pointer",
        }}
      >
        {anyUploading ? "Uploading…" : "Done"}
      </button>
    </BottomSheet>
  );
}
