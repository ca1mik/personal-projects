"use client";

import { useEffect, useRef, useState } from "react";

const CAMERA_PRESETS = [
  { label: "Front", azimuth: 0, elevation: 82, radiusMultiplier: 1.18 },
  { label: "Left", azimuth: 90, elevation: 82, radiusMultiplier: 1.18 },
  { label: "Back", azimuth: 180, elevation: 82, radiusMultiplier: 1.18 },
  { label: "Right", azimuth: 270, elevation: 82, radiusMultiplier: 1.18 },
  { label: "Top", azimuth: 0, elevation: 14, radiusMultiplier: 1.42 }
] as const;

function formatMeters(value: number): string {
  return `${value.toFixed(3)}m`;
}

function buildCameraOrbit(
  preset: (typeof CAMERA_PRESETS)[number],
  dimensions: { x: number; y: number; z: number }
): string {
  const maxDimension = Math.max(dimensions.x, dimensions.y, dimensions.z, 0.01);
  const radius = Math.max(0.65, maxDimension * preset.radiusMultiplier);
  return `${preset.azimuth}deg ${preset.elevation}deg ${formatMeters(radius)}`;
}

export function ModelViewerPanel({ src, alt }: { src: string | null; alt: string }) {
  const [ready, setReady] = useState(false);
  const [activePreset, setActivePreset] = useState<(typeof CAMERA_PRESETS)[number]["label"]>("Front");
  const [cameraOrbit, setCameraOrbit] = useState("0deg 82deg 2.000m");
  const [cameraTarget, setCameraTarget] = useState("0.000m 0.000m 0.000m");
  const [autoRotate, setAutoRotate] = useState(true);
  const viewerRef = useRef<HTMLElementTagNameMap["model-viewer"] | null>(null);

  useEffect(() => {
    let active = true;
    void import("@google/model-viewer").then(() => {
      if (active) {
        setReady(true);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!ready || !src) {
      return;
    }

    const viewer = viewerRef.current;
    if (!viewer) {
      return;
    }

    let cancelled = false;

    const syncFraming = async () => {
      try {
        await viewer.updateFraming();
        if (cancelled) {
          return;
        }

        const preset = CAMERA_PRESETS.find((item) => item.label === activePreset) ?? CAMERA_PRESETS[0];
        const center = viewer.getBoundingBoxCenter();
        const dimensions = viewer.getDimensions();
        const nextTarget = `${formatMeters(center.x)} ${formatMeters(center.y)} ${formatMeters(center.z)}`;
        const nextOrbit = buildCameraOrbit(preset, dimensions);

        setCameraTarget(nextTarget);
        setCameraOrbit(nextOrbit);
        viewer.cameraTarget = nextTarget;
        viewer.fieldOfView = "18deg";
        viewer.cameraOrbit = nextOrbit;
        viewer.jumpCameraToGoal();
      } catch {
        // The viewer silently ignores framing updates while it is still loading.
      }
    };

    const handleLoad = () => {
      void syncFraming();
    };

    viewer.addEventListener("load", handleLoad);
    void syncFraming();

    return () => {
      cancelled = true;
      viewer.removeEventListener("load", handleLoad);
    };
  }, [activePreset, ready, src]);

  if (!src) {
    return (
      <div className="empty-state viewer-empty">
        <p>No GLB preview yet.</p>
        <span>The browser preview appears here as soon as a job writes `model.glb`.</span>
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="empty-state viewer-empty">
        <p>Loading viewer...</p>
        <span>The GLB is ready. The browser component is being initialized.</span>
      </div>
    );
  }

  return (
    <>
      <div className="viewer-toolbar">
        {CAMERA_PRESETS.map((preset) => (
          <button
            key={preset.label}
            className={`ghost-button viewer-angle-button ${activePreset === preset.label ? "active" : ""}`}
            type="button"
            onClick={() => {
              setActivePreset(preset.label);
              const viewer = viewerRef.current;
              if (viewer) {
                const center = viewer.getBoundingBoxCenter();
                const dimensions = viewer.getDimensions();
                const nextTarget = `${formatMeters(center.x)} ${formatMeters(center.y)} ${formatMeters(center.z)}`;
                const nextOrbit = buildCameraOrbit(preset, dimensions);

                setCameraTarget(nextTarget);
                setCameraOrbit(nextOrbit);
                viewer.cameraTarget = nextTarget;
                viewer.cameraOrbit = nextOrbit;
                viewer.fieldOfView = "18deg";
                viewer.jumpCameraToGoal();
              }
            }}
          >
            {preset.label}
          </button>
        ))}
        <button
          className={`ghost-button viewer-angle-button ${autoRotate ? "active" : ""}`}
          type="button"
          onClick={() => setAutoRotate((current) => !current)}
        >
          {autoRotate ? "Pause turntable" : "Start turntable"}
        </button>
        <span className="viewer-hint">Drag to orbit, scroll to zoom, or use the preset angles.</span>
      </div>
      <div className="viewer-frame">
        <model-viewer
          ref={viewerRef}
          alt={alt}
          src={src}
          camera-controls
          disable-pan
          exposure="0.9"
          shadow-intensity="1"
          environment-image="neutral"
          field-of-view="18deg"
          camera-orbit={cameraOrbit}
          camera-target={cameraTarget}
          auto-rotate={autoRotate || undefined}
          className="model-viewer-element"
        />
      </div>
    </>
  );
}
