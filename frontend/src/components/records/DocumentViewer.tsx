"use client";

import { useEffect, useState } from "react";

interface DocumentViewerProps {
  url: string;
  title: string;
  onClose: () => void;
}

export default function DocumentViewer({ url, title, onClose }: DocumentViewerProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [mimeType, setMimeType] = useState<string>("application/octet-stream");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    let objectUrl: string | null = null;
    setLoading(true);
    setError(false);
    setBlobUrl(null);

    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const ct = res.headers.get("content-type") || "application/octet-stream";
        setMimeType(ct.split(";")[0].trim());
        return res.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
        setError(true);
      });

    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  const isImage = mimeType.startsWith("image/");

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 999,
        background: "rgba(0,0,0,0.92)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 16px",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            color: "#fff",
            fontSize: 14,
            fontWeight: 600,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            maxWidth: "calc(100% - 48px)",
          }}
        >
          {title}
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close document viewer"
          style={{
            width: 36,
            height: 36,
            borderRadius: 999,
            border: "none",
            background: "rgba(255,255,255,0.15)",
            color: "#fff",
            fontSize: 20,
            lineHeight: "36px",
            cursor: "pointer",
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          ×
        </button>
      </div>

      <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        {loading && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontSize: 14,
            }}
          >
            Opening document…
          </div>
        )}

        {error && !loading && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 12,
              color: "#fff",
              fontSize: 14,
            }}
          >
            <span>Could not display this document inline.</span>
            <a
              href={url}
              download
              style={{
                background: "#fff",
                color: "#111",
                borderRadius: 8,
                padding: "8px 20px",
                fontWeight: 600,
                fontSize: 13,
                textDecoration: "none",
              }}
            >
              Download file →
            </a>
          </div>
        )}

        {blobUrl && !loading && !error && (
          isImage ? (
            <img
              src={blobUrl}
              alt={title}
              style={{
                maxWidth: "100%",
                maxHeight: "100%",
                objectFit: "contain",
                display: "block",
                margin: "auto",
              }}
            />
          ) : (
            <iframe
              src={blobUrl}
              title={title}
              style={{
                width: "100%",
                height: "100%",
                border: "none",
                background: "#fff",
              }}
            />
          )
        )}
      </div>
    </div>
  );
}
