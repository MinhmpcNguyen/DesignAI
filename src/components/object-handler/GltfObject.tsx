"use client";

import { useGLTF } from "@react-three/drei";
import { useThree } from "@react-three/fiber";
import { Component, type ReactNode, useMemo } from "react";
import { DoubleSide, Mesh, MeshPhysicalMaterial, type Material } from "three";
import { KTX2Loader } from "three-stdlib";
import {
  buildRuntimeNormalizeOptions,
  normalizeGltfRoot,
} from "@/lib/gltfNormalize";

// Module-level singleton — created once, reused for every useGLTF call.
let _ktx2Loader: KTX2Loader | null = null;

// ---------------------------------------------------------------------------
// GltfErrorBoundary — catches useGLTF() load failures (404, network error,
// malformed GLB) and renders a fallback mesh instead of crashing the scene.
// ---------------------------------------------------------------------------
interface GltfErrorBoundaryProps {
  modelUrl: string;
  fallback: ReactNode;
  children: ReactNode;
}

export class GltfErrorBoundary extends Component<
  GltfErrorBoundaryProps,
  { hasError: boolean }
> {
  state = { hasError: false };
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(error: Error) {
    console.error("[GltfObject] Failed to load model", {
      modelUrl: this.props.modelUrl,
      message: error.message,
    });
  }
  render() {
    return this.state.hasError ? this.props.fallback : this.props.children;
  }
}

interface GltfObjectProps {
  modelUrl: string;
  size: [number, number, number];
  color?: string;
  is2D?: boolean;
  /** When true, mesh/material names containing "glass" use transmission for see-through glazing. */
  applyGlassMaterials?: boolean;
  onClick?: (e: import("@react-three/fiber").ThreeEvent<MouseEvent>) => void;
}

const GLASS_NAME_RE = /glass|kính|kinh|window|fenster/i;

function looksLikeGlassMesh(mesh: Mesh): boolean {
  const n = mesh.name ?? "";
  if (GLASS_NAME_RE.test(n)) return true;
  const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
  for (const m of mats) {
    if (!m) continue;
    if ("name" in m && typeof m.name === "string" && GLASS_NAME_RE.test(m.name))
      return true;
    if (
      "transparent" in m &&
      (m as { transparent?: boolean }).transparent === true
    )
      return true;
    if (
      "opacity" in m &&
      typeof (m as { opacity?: number }).opacity === "number" &&
      (m as { opacity: number }).opacity < 0.98
    )
      return true;
  }
  return false;
}

function toGlassPhysicalMaterial(source: Material): MeshPhysicalMaterial {
  const g = new MeshPhysicalMaterial();
  if ("color" in source && source.color) g.color.copy(source.color as never);
  g.transmission = 0.92;
  g.thickness = 0.25;
  g.roughness = 0.08;
  g.metalness = 0;
  g.transparent = true;
  g.opacity = 1;
  g.side = DoubleSide;
  g.envMapIntensity = 1;
  return g;
}

/**
 * Renders a .glb model loaded via useGLTF (lazy, cached).
 *
 * Normalization strategy (shared with thumbnail renderer):
 * - reset root transforms to a clean baseline,
 * - scale model to declared catalog size (per-axis),
 * - center on X/Z to keep mesh aligned with gizmo,
 * - align model bottom to local Y = -(size[1] / 2) so it sits on the floor.
 *
 * Selection highlight is handled by the parent MovableObject (wireframe mesh),
 * so this component never mutates shared GLB materials.
 */
export default function GltfObject({
  modelUrl,
  size,
  is2D = false,
  applyGlassMaterials = false,
  onClick,
}: GltfObjectProps) {
  const { gl } = useThree();

  const { scene } = useGLTF(modelUrl, true, true, (loader) => {
    if (!_ktx2Loader) {
      _ktx2Loader = new KTX2Loader();
      _ktx2Loader.setTranscoderPath("/basis/");
      _ktx2Loader.detectSupport(gl);
    }
    loader.setKTX2Loader(_ktx2Loader);
  });

  // Re-clone only when the URL, declared size, or view mode changes.
  // isSelected is intentionally omitted — selection highlight is rendered
  // as a wireframe overlay by the parent MovableObject, which avoids
  // swapping the primitive's Three.js object on every selection change and
  // ensures click handlers stay reliably registered.
  const cloned = useMemo(() => {
    const clone = scene.clone(true);
    normalizeGltfRoot(clone, buildRuntimeNormalizeOptions(modelUrl, size));

    clone.traverse((child) => {
      if (!(child instanceof Mesh)) return;
      child.castShadow = !is2D;
      child.receiveShadow = !is2D;
      if (applyGlassMaterials && looksLikeGlassMesh(child)) {
        const mats = Array.isArray(child.material)
          ? child.material
          : [child.material];
        const next = mats.map((m) =>
          m ? toGlassPhysicalMaterial(m) : m,
        ) as Material[];
        child.material = next.length === 1 ? next[0]! : next;
      }
    });

    return clone;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelUrl, size[0], size[1], size[2], is2D, applyGlassMaterials]);

  return <primitive object={cloned} onClick={onClick} />;
}
