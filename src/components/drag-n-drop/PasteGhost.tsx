"use client";

import { useEffect, useRef, useState, useMemo, type ReactElement } from "react";
import { useThree } from "@react-three/fiber";
import {
  useClipboardValue,
  useSetIsPasting,
} from "@/states/slices/clipboard/hooks";
import { useAddMultipleObjects } from "@/states/slices/objects/hooks";
import type { SceneObject } from "@/states/slices/objects/types";
import { Plane, Vector2, Vector3 } from "three";

/** Plane y=1 for paste placement (object center height) */
const PASTE_PLANE = new Plane(new Vector3(0, 1, 0), -1);

/**
 * Shows a ghost preview of the copied object(s) that follows the mouse cursor.
 * Click to place the object(s) at the current position.
 * Supports multi-object paste with maintains relative positions.
 */
export default function PasteGhost() {
  const { copiedObjects, isPasting } = useClipboardValue();
  const setIsPasting = useSetIsPasting();
  const addMultipleObjects = useAddMultipleObjects();
  const { camera, gl, raycaster } = useThree();

  const [ghostPosition, setGhostPosition] = useState<[number, number, number]>([
    0, 1, 0,
  ]);
  const intersectionRef = useRef(new Vector3());

  // Calculate center point of copied objects for positioning
  const objectsCenter = useMemo(() => {
    if (copiedObjects.length === 0)
      return [0, 1, 0] as [number, number, number];

    const sum = copiedObjects.reduce(
      (acc, obj) => {
        acc[0] += obj.position[0];
        acc[1] += obj.position[1];
        acc[2] += obj.position[2];
        return acc;
      },
      [0, 0, 0],
    );

    return [
      sum[0] / copiedObjects.length,
      sum[1] / copiedObjects.length,
      sum[2] / copiedObjects.length,
    ] as [number, number, number];
  }, [copiedObjects]);

  useEffect(() => {
    if (!isPasting || copiedObjects.length === 0) return;

    const handleMouseMove = (event: MouseEvent) => {
      // Convert client coordinates to NDC
      const rect = gl.domElement.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      const mouse = new Vector2(x, y);
      raycaster.setFromCamera(mouse, camera);

      const hit = raycaster.ray.intersectPlane(
        PASTE_PLANE,
        intersectionRef.current,
      );

      if (hit) {
        setGhostPosition([hit.x, objectsCenter[1], hit.z]);
      }
    };

    const handleClick = (event: MouseEvent) => {
      // Prevent triggering if clicking on UI elements
      if ((event.target as HTMLElement).tagName !== "CANVAS") return;

      // Calculate offset from center to paste position
      const offsetX = ghostPosition[0] - objectsCenter[0];
      const offsetZ = ghostPosition[2] - objectsCenter[2];

      // Create new objects at ghost position, maintaining relative positions
      const newObjects: SceneObject[] = copiedObjects.map((obj) => ({
        ...obj,
        id: `obj-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        position: [
          obj.position[0] + offsetX,
          obj.position[1],
          obj.position[2] + offsetZ,
        ],
      }));

      addMultipleObjects(newObjects);
      setIsPasting(false); // Exit paste mode
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("click", handleClick);

    // Change cursor to indicate paste mode
    document.body.style.cursor = "crosshair";

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("click", handleClick);
      document.body.style.cursor = "default";
    };
  }, [
    isPasting,
    copiedObjects,
    ghostPosition,
    objectsCenter,
    camera,
    raycaster,
    gl,
    addMultipleObjects,
    setIsPasting,
  ]);

  // Memoize geometry generation for all copied objects
  const ghostMeshes = useMemo(() => {
    if (copiedObjects.length === 0) return null;

    // Calculate offset from center to each object
    const offsetX = ghostPosition[0] - objectsCenter[0];
    const offsetZ = ghostPosition[2] - objectsCenter[2];

    return copiedObjects.map((obj, index) => {
      const geometry: ReactElement = <boxGeometry args={obj.size} />;

      const position: [number, number, number] = [
        obj.position[0] + offsetX,
        obj.position[1],
        obj.position[2] + offsetZ,
      ];

      return (
        <mesh key={index} position={position}>
          {geometry}
          <meshStandardMaterial
            color={obj.color}
            transparent
            opacity={0.5}
            wireframe
          />
        </mesh>
      );
    });
  }, [copiedObjects, ghostPosition, objectsCenter]);

  // Don't render anything if not in paste mode or no copied objects
  if (!isPasting || copiedObjects.length === 0) return null;

  return <group>{ghostMeshes}</group>;
}
