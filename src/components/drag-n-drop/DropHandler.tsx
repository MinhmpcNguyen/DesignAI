"use client";

import { useEffect, useRef } from "react";
import { useThree } from "@react-three/fiber";
import {
  usePendingDrop,
  useSetPendingDrop,
  useAddObject,
} from "@/states/slices/objects/hooks";
import type { SceneObject } from "@/states/slices/objects/types";
import { useCalculateSnap } from "@/states/slices/snapping";
import { getFurnitureMetadata } from "@/states/slices/snapping";
import { Plane, Raycaster, Vector2, Vector3 } from "three";

/** Plane y=1 for drop placement (object center height) */
const DROP_PLANE = new Plane(new Vector3(0, 1, 0), -1);
const INTERSECTION = new Vector3();

/**
 * Runs inside Canvas. When a pending drop exists, raycasts from mouse to plane y=1
 * and adds the object at that position.
 *
 * Snapping integration:
 * - Calculates snapped position before placing object
 * - Includes snapping metadata in created object
 */
export default function DropHandler() {
  const pendingDrop = usePendingDrop();
  const setPendingDrop = useSetPendingDrop();
  const addObject = useAddObject();
  const calculateSnap = useCalculateSnap();
  const { camera, gl } = useThree();
  const raycasterRef = useRef(new Raycaster());
  const ndcRef = useRef(new Vector2());

  useEffect(() => {
    if (!pendingDrop) return;

    const raycaster = raycasterRef.current;
    const ndc = ndcRef.current;
    const canvas = gl.domElement;
    const rect = canvas.getBoundingClientRect();

    ndc.x = ((pendingDrop.clientX - rect.left) / rect.width) * 2 - 1;
    ndc.y = -((pendingDrop.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(ndc, camera);
    const hit = raycaster.ray.intersectPlane(DROP_PLANE, INTERSECTION);

    // Raw position from raycast
    const rawPosition: [number, number, number] = hit
      ? [hit.x, hit.y, hit.z]
      : [0, 1, 0];

    const objectSize: [number, number, number] = [1, 1, 1];

    // For wall objects, set initial Y to wallMountHeight so the first placement
    // is at the correct height. During subsequent drags, position[1] is preserved.
    const shapeMetadata = getFurnitureMetadata(pendingDrop.shape);
    const initialPosition: [number, number, number] = [
      rawPosition[0],
      shapeMetadata?.placement === "wall"
        ? (shapeMetadata.wallMountHeight ?? 1.5)
        : rawPosition[1],
      rawPosition[2],
    ];

    // Calculate snapped position
    const snapResult = calculateSnap(
      pendingDrop.shape,
      initialPosition,
      objectSize,
    );

    const newObj: SceneObject = {
      id: `obj-${Date.now()}`,
      name: pendingDrop.name,
      type: pendingDrop.shape,
      position: snapResult.position,
      rotation: snapResult.rotation ?? [0, 0, 0, 1],
      color: "#4a90e2",
      size: objectSize,
      modelUrl: pendingDrop.modelUrl,
      placementType: snapResult.snappedTo ?? undefined,
      snappedToWall: snapResult.wallType,
      catalogItemId: pendingDrop.catalogItemId,
    };
    addObject(newObj);
    setPendingDrop(null);
  }, [pendingDrop, camera, gl, addObject, setPendingDrop, calculateSnap]);

  return null;
}
