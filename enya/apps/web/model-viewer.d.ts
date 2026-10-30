import type * as React from "react";
import type { ModelViewerElement } from "@google/model-viewer";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "model-viewer": React.DetailedHTMLProps<React.HTMLAttributes<ModelViewerElement>, ModelViewerElement> & {
        src?: string;
        alt?: string;
        poster?: string;
        "camera-controls"?: boolean;
        "camera-orbit"?: string;
        "camera-target"?: string;
        "auto-rotate"?: boolean;
        "disable-pan"?: boolean;
        "disable-zoom"?: boolean;
        "field-of-view"?: string;
        "min-camera-orbit"?: string;
        "max-camera-orbit"?: string;
        "shadow-intensity"?: string;
        exposure?: string;
        "environment-image"?: string;
        loading?: "eager" | "lazy";
      };
    }
  }
}

export {};
