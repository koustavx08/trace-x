"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  // Next.js renders global-error.tsx in place of the root layout when an
  // error escapes it, so it must define its own <html>/<body> - it cannot
  // rely on app/layout.tsx being mounted.
  return (
    <html lang="en">
      <body
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0a0f1a",
          color: "#e5e7eb",
          fontFamily: "system-ui, sans-serif",
          padding: "1.5rem",
        }}
      >
        <div
          style={{
            maxWidth: "28rem",
            width: "100%",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "1rem",
            border: "1px solid #1f2937",
            borderRadius: "0.75rem",
            padding: "2rem",
            background: "#111827",
          }}
        >
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, margin: 0 }}>Application Error</h1>
          <p style={{ fontSize: "0.875rem", color: "#9ca3af", margin: 0 }}>
            {error.message || "A critical error occurred and the application could not recover."}
          </p>
          <button
            onClick={() => reset()}
            style={{
              height: "2.5rem",
              padding: "0 1rem",
              borderRadius: "0.375rem",
              fontWeight: 500,
              background: "#3b82f6",
              color: "#fff",
              border: "none",
              cursor: "pointer",
            }}
          >
            Try Again
          </button>
        </div>
      </body>
    </html>
  );
}
