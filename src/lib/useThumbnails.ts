import { useState, useEffect } from "react";
import { renderModelThumbnail } from "./thumbnailRenderer";

/**
 * Sequentially renders thumbnails for a list of model URLs using the shared
 * offscreen renderer, updating state as each one finishes.
 * Results are internally cached — re-mounting the component is instant.
 */
export function useThumbnails(modelUrls: string[]): Map<string, string> {
  const [thumbnails, setThumbnails] = useState<Map<string, string>>(new Map());

  // Stable string key so the effect only re-fires when the URL list changes
  const urlsKey = modelUrls.join("|");

  useEffect(() => {
    if (modelUrls.length === 0) return;
    let cancelled = false;

    (async () => {
      for (const url of modelUrls) {
        if (cancelled) break;
        try {
          const dataUrl = await renderModelThumbnail(url);
          if (!cancelled && dataUrl) {
            setThumbnails((prev) => new Map(prev).set(url, dataUrl));
          }
        } catch {
          // skip items that fail to load — color swatch fallback stays visible
        }
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlsKey]);

  return thumbnails;
}
