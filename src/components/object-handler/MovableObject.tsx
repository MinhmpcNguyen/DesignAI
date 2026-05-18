"use client";

import {
  useRef,
  useState,
  useLayoutEffect,
  useEffect,
  memo,
  useMemo,
  Suspense,
} from "react";
import { PivotControls } from "@react-three/drei";
import {
  useIsObjectSelected,
  useIsCtrlPressed,
  useIsPrimarySelected,
  useSelectObjectOrGroup,
  useToggleObjectOrGroup,
  useSelectionValue,
} from "@/states/slices/selection/hooks";
import {
  useMoveObjectLive,
  useMoveObjectRotationLive,
  useMoveGroupPositionsLive,
  useCommitObjectAfterDrag,
} from "@/states/slices/objects/hooks";
import {
  useObjectGroupId,
  useGroupById,
  useIsGroupFullySelected,
} from "@/states/slices/groups/hooks";
import { useViewMode } from "@/states/slices/view/hooks";
import { ThreeEvent } from "@react-three/fiber";
import {
  useCalculateSnap,
  getFurnitureMetadata,
} from "@/states/slices/snapping";
import GltfObject, {
  GltfErrorBoundary,
} from "@/components/object-handler/GltfObject";
import ResizeHandles from "@/components/object-handler/ResizeHandles";
import { getSnapFurnitureType } from "@/lib/doorModels";
import type { SceneObject } from "@/states/slices/objects/types";
import { Euler, Group, Matrix4, Quaternion, Vector3 } from "three";
import { objectInteractionFlag } from "@/states/objectInteractionFlag";
import { isResizable } from "@/constant/resizeConfig";

interface MovableObjectProps {
  id: string;
  position?: [number, number, number];
  rotation?: [number, number, number, number];
  shape: "model";
  color?: string;
  size?: [number, number, number] | number;
  modelUrl?: string;
  name?: string;
  /** Per-catalog-item placement override — used so 'model'-type wall/ceiling items snap correctly */
  placementType?: "floor" | "wall" | "ceiling";
  objectRole?: SceneObject["objectRole"];
  snappedToWall?: string;
  collisionLayer?: SceneObject["collisionLayer"];
  placeOn?: SceneObject["placeOn"];
}

/**
 * Draggable 3D object (no physics).
 * PivotControls drives the object's transform directly.
 * Supports selection with visual highlight.
 * Memoized for performance - only re-renders when props change.
 */
const MovableObject = memo(
  function MovableObject({
    id,
    position = [0, 1, 0],
    rotation = [0, 0, 0, 1],
    shape,
    color = "#4a90e2",
    size = 1,
    modelUrl,
    placementType,
    objectRole,
    snappedToWall,
    collisionLayer,
    name,
  }: MovableObjectProps) {
    const groupRef = useRef<Group | null>(null);
    const previousPositionRef = useRef<[number, number, number]>(position);

    // Selection state — granular selectors, only this object re-renders on its own state change
    const isSelected = useIsObjectSelected(id);
    const isCtrlPressed = useIsCtrlPressed();
    const shouldShowHandle = useIsPrimarySelected(id);
    const selectObjectOrGroup = useSelectObjectOrGroup();
    const toggleObjectOrGroup = useToggleObjectOrGroup();
    // Commit dispatcher — used at onDragEnd only (pushes one history entry)
    const commitObjectAfterDrag = useCommitObjectAfterDrag();

    // Live dispatchers — update state without pushing to history (drag frames)
    const moveObjectLive = useMoveObjectLive();
    const moveObjectRotationLive = useMoveObjectRotationLive();
    const moveGroupPositionsLive = useMoveGroupPositionsLive();

    const calculateSnap = useCalculateSnap();
    const viewMode = useViewMode();

    // Multi-select state — keep a ref so onDrag closure always reads fresh value
    const { selectedIds } = useSelectionValue();
    const selectedIdsRef = useRef<Set<string>>(selectedIds);
    useEffect(() => {
      selectedIdsRef.current = selectedIds;
    }, [selectedIds]);

    // Group state — granular selectors
    const groupId = useObjectGroupId(id);
    const group = useGroupById(groupId);
    const isInSelectedGroup = useIsGroupFullySelected(groupId);
    const is2D = viewMode === "2D";
    const hiddenSurfaceChildIn2D = is2D && collisionLayer === "surface_child";

    const isDoorObject = objectRole === "door";
    const isWindowObject = objectRole === "window";
    /** 2D doors/windows: pick via plan symbol fill, not tall bounding box. */
    const door2DBlockRaycast = is2D && (isDoorObject || isWindowObject);
    const snapFurnitureType = getSnapFurnitureType(shape, objectRole);
    /** Doors and windows must stay on a wall (nearest wall when dragged). */
    const doorWallLock = objectRole === "door" || objectRole === "window";
    const wallSnapAlways = doorWallLock ? Number.POSITIVE_INFINITY : undefined;

    const lastGoodDoorWallPosRef = useRef<[number, number, number]>(position);
    const lastGoodDoorWallRotRef =
      useRef<[number, number, number, number]>(rotation);
    const lastGoodDoorWallIdRef = useRef<string | undefined>(undefined);

    const [isDraggingResize, setIsDraggingResize] = useState(false);

    const [matrix] = useState(() => {
      const m = new Matrix4();
      m.compose(
        new Vector3(position[0], position[1], position[2]),
        new Quaternion(rotation[0], rotation[1], rotation[2], rotation[3]),
        new Vector3(1, 1, 1),
      );
      return m;
    });
    // Persistent refs so onDragEnd always has valid scale even across re-renders
    const vecRef = useRef(new Vector3());
    const rotRef = useRef(new Quaternion());
    const sclRef = useRef(new Vector3(1, 1, 1));
    // Tracks the live Y-axis rotation applied during drag so onDragEnd can persist it
    const liveRotRef = useRef(
      new Quaternion(rotation[0], rotation[1], rotation[2], rotation[3]),
    );

    const lockedRotation = useMemo(
      () => new Quaternion(rotation[0], rotation[1], rotation[2], rotation[3]),
      [rotation],
    );

    useLayoutEffect(() => {
      matrix.compose(
        new Vector3(position[0], position[1], position[2]),
        new Quaternion(rotation[0], rotation[1], rotation[2], rotation[3]),
        new Vector3(1, 1, 1),
      );
      if (groupRef.current) {
        groupRef.current.position.set(position[0], position[1], position[2]);
        groupRef.current.quaternion.set(
          rotation[0],
          rotation[1],
          rotation[2],
          rotation[3],
        );
      }
      // Update previous position ref when position changes externally
      previousPositionRef.current = position;
      // Keep liveRotRef in sync so the next PivotControls drag starts from the correct rotation
      // (important when rotation was changed externally, e.g. via the number input in SelectedObjectOverlay)
      liveRotRef.current.set(
        rotation[0],
        rotation[1],
        rotation[2],
        rotation[3],
      );
      if (doorWallLock) {
        lastGoodDoorWallPosRef.current = position;
        lastGoodDoorWallRotRef.current = rotation;
        if (snappedToWall) lastGoodDoorWallIdRef.current = snappedToWall;
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [position, rotation, doorWallLock, snappedToWall]);

    // Handle click to select (group-aware)
    const handleClick = (e: ThreeEvent<MouseEvent>) => {
      e.stopPropagation(); // Prevent canvas click from deselecting

      if (isCtrlPressed) {
        // Ctrl+Click: Toggle this object/group in the selection
        toggleObjectOrGroup(id);
      } else {
        // Regular click: Select this object/group (clears others)
        selectObjectOrGroup(id);
      }
    };

    // Render geometry based on shape - memoized to prevent recreation
    const renderGeometry = useMemo(() => {
      const modelSize =
        typeof size === "number"
          ? ([size, size, size] as [number, number, number])
          : size;
      return <boxGeometry args={modelSize} />;
    }, [size]);

    // Determine rotation axes based on placement type
    // placementType prop overrides shape-level metadata for 'model' catalog items
    const isFloorObject = useMemo(() => {
      if (placementType) return placementType === "floor";
      const metadata = getFurnitureMetadata(shape);
      return metadata?.placement === "floor";
    }, [shape, placementType]);

    const isWallObject = useMemo(() => {
      if (placementType) return placementType === "wall";
      const metadata = getFurnitureMetadata(shape);
      return metadata?.placement === "wall";
    }, [shape, placementType]);

    const isCeilingObject = useMemo(() => {
      if (placementType) return placementType === "ceiling";
      const metadata = getFurnitureMetadata(shape);
      return metadata?.placement === "ceiling";
    }, [shape, placementType]);

    if (hiddenSurfaceChildIn2D) {
      return null;
    }

    return (
      <group>
        {shouldShowHandle && !isDraggingResize && (
          <PivotControls
            matrix={matrix}
            scale={1.5}
            activeAxes={[true, true, true]} // Enable all movement axes (X, Y, Z)
            disableRotations={!isFloorObject} // Allow Y-axis rotation for floor objects
            depthTest={false}
            onDragStart={() => {
              // Prevent MouseDragSelect from starting a marquee when the user
              // clicks on a PivotControls handle (the handle mesh is not the
              // furniture mesh, so onPointerDown never fires on it).
              objectInteractionFlag.active = true;
            }}
            onDrag={(local) => {
              local.decompose(vecRef.current, rotRef.current, sclRef.current);
              const vec = vecRef.current;
              const rot = rotRef.current;
              const scl = sclRef.current;

              if (
                Number.isNaN(vec.x) ||
                Number.isNaN(vec.y) ||
                Number.isNaN(vec.z)
              ) {
                return;
              }

              matrix.copy(local);
              // For floor objects: allow Y-axis rotation (spinning on the floor).
              // For all others: keep rotation locked.
              let effectiveRot: Quaternion;
              if (isFloorObject) {
                const euler = new Euler().setFromQuaternion(rot, "YXZ");
                effectiveRot = new Quaternion().setFromEuler(
                  new Euler(0, euler.y, 0),
                );
                liveRotRef.current = effectiveRot.clone();
              } else {
                effectiveRot = lockedRotation.clone();
              }
              rot.copy(effectiveRot);
              if (groupRef.current) {
                groupRef.current.position.copy(vec);
                groupRef.current.quaternion.copy(effectiveRot);
              }

              const newPosition: [number, number, number] = [
                vec.x,
                vec.y,
                vec.z,
              ];

              // Apply snapping during drag for floor objects
              if (isFloorObject) {
                const objectSize: [number, number, number] =
                  typeof size === "number"
                    ? [size, size, size]
                    : (size as [number, number, number]);

                const snapResult = calculateSnap(
                  snapFurnitureType,
                  newPosition,
                  objectSize,
                  placementType,
                  wallSnapAlways,
                );

                if (snapResult.snappedTo) {
                  // Use snapped position
                  newPosition[1] = snapResult.position[1];

                  // Update groupRef to snapped position
                  if (groupRef.current) {
                    groupRef.current.position.setY(snapResult.position[1]);
                  }

                  // Update matrix to reflect snap (keeps handle at correct position)
                  const snappedVec = new Vector3(
                    newPosition[0],
                    snapResult.position[1],
                    newPosition[2],
                  );
                  matrix.compose(snappedVec, effectiveRot, scl);
                }
              }

              // Apply snapping during drag for ceiling objects
              if (isCeilingObject) {
                const objectSize: [number, number, number] =
                  typeof size === "number"
                    ? [size, size, size]
                    : (size as [number, number, number]);

                const snapResult = calculateSnap(
                  snapFurnitureType,
                  newPosition,
                  objectSize,
                  "ceiling",
                );

                if (snapResult.snappedTo === "ceiling") {
                  newPosition[1] = snapResult.position[1];
                  if (groupRef.current) {
                    groupRef.current.position.setY(snapResult.position[1]);
                  }
                  const snappedVec = new Vector3(
                    newPosition[0],
                    snapResult.position[1],
                    newPosition[2],
                  );
                  matrix.compose(snappedVec, effectiveRot, scl);
                }
              }

              // Apply snapping during drag for wall objects (real-time position + rotation)
              if (isWallObject) {
                const objectSize: [number, number, number] =
                  typeof size === "number"
                    ? [size, size, size]
                    : (size as [number, number, number]);

                const snapResult = calculateSnap(
                  snapFurnitureType,
                  newPosition,
                  objectSize,
                  placementType,
                  wallSnapAlways,
                );

                if (snapResult.snappedTo === "wall") {
                  newPosition[0] = snapResult.position[0];
                  newPosition[1] = snapResult.position[1];
                  newPosition[2] = snapResult.position[2];

                  const snapQuat = snapResult.rotation
                    ? new Quaternion(
                        snapResult.rotation[0],
                        snapResult.rotation[1],
                        snapResult.rotation[2],
                        snapResult.rotation[3],
                      )
                    : lockedRotation;

                  if (groupRef.current) {
                    groupRef.current.position.set(
                      newPosition[0],
                      newPosition[1],
                      newPosition[2],
                    );
                    groupRef.current.quaternion.copy(snapQuat);
                  }

                  matrix.compose(
                    new Vector3(newPosition[0], newPosition[1], newPosition[2]),
                    snapQuat,
                    scl,
                  );

                  if (snapResult.rotation) {
                    moveObjectRotationLive(id, snapResult.rotation);
                  }

                  if (doorWallLock && snapResult.wallType) {
                    lastGoodDoorWallPosRef.current = [...newPosition];
                    if (snapResult.rotation) {
                      lastGoodDoorWallRotRef.current = snapResult.rotation;
                    }
                    lastGoodDoorWallIdRef.current = snapResult.wallType;
                  }
                } else if (doorWallLock) {
                  const p = lastGoodDoorWallPosRef.current;
                  const rq = lastGoodDoorWallRotRef.current;
                  const snapQuat = new Quaternion(rq[0], rq[1], rq[2], rq[3]);
                  newPosition[0] = p[0];
                  newPosition[1] = p[1];
                  newPosition[2] = p[2];
                  if (groupRef.current) {
                    groupRef.current.position.set(p[0], p[1], p[2]);
                    groupRef.current.quaternion.copy(snapQuat);
                  }
                  matrix.compose(new Vector3(p[0], p[1], p[2]), snapQuat, scl);
                }
              }

              // Calculate position delta (needed for group and multi-select moves)
              const delta: [number, number, number] = [
                newPosition[0] - previousPositionRef.current[0],
                newPosition[1] - previousPositionRef.current[1],
                newPosition[2] - previousPositionRef.current[2],
              ];

              if (isInSelectedGroup && group) {
                // Update all group members with the same delta (optimized - no O(n*m) search)
                moveGroupPositionsLive({
                  objectIds: group.objectIds,
                  delta,
                });
              } else if (selectedIdsRef.current.size > 1) {
                // Non-grouped multi-select: move all selected objects by the same delta
                moveGroupPositionsLive({
                  objectIds: Array.from(selectedIdsRef.current),
                  delta,
                });
              } else {
                // Single object update
                moveObjectLive(id, newPosition);
              }

              // Update previous position
              previousPositionRef.current = newPosition;
            }}
            onDragEnd={() => {
              // Release the flag so marquee selection works again after drag
              objectInteractionFlag.active = false;
              // Re-snap object to nearest snap target after drag ends
              const currentPosition = previousPositionRef.current;
              const objectSize: [number, number, number] =
                typeof size === "number"
                  ? [size, size, size]
                  : (size as [number, number, number]);

              const snapResult = calculateSnap(
                snapFurnitureType,
                currentPosition,
                objectSize,
                placementType,
                wallSnapAlways,
              );

              if (snapResult.snappedTo) {
                // Commit position + rotation + snap in a single history push.
                // Floor snap never provides a rotation (only adjusts Y), so fall back to
                // liveRotRef which holds the Y-axis rotation accumulated during this drag.
                const committedRotation:
                  | [number, number, number, number]
                  | undefined =
                  snapResult.rotation ??
                  (isFloorObject
                    ? [
                        liveRotRef.current.x,
                        liveRotRef.current.y,
                        liveRotRef.current.z,
                        liveRotRef.current.w,
                      ]
                    : undefined);
                commitObjectAfterDrag({
                  id,
                  position: snapResult.position,
                  rotation: committedRotation,
                  placementType: snapResult.snappedTo,
                  snappedToWall: snapResult.wallType,
                });

                // Sync matrix so PivotControls handles align to snapped position/rotation
                const snappedRot = snapResult.rotation
                  ? new Quaternion(
                      snapResult.rotation[0],
                      snapResult.rotation[1],
                      snapResult.rotation[2],
                      snapResult.rotation[3],
                    )
                  : isFloorObject
                    ? liveRotRef.current.clone()
                    : lockedRotation;
                matrix.compose(
                  new Vector3(
                    snapResult.position[0],
                    snapResult.position[1],
                    snapResult.position[2],
                  ),
                  snappedRot,
                  sclRef.current,
                );

                // Update previous position ref
                previousPositionRef.current = snapResult.position;

                if (doorWallLock && snapResult.snappedTo === "wall") {
                  lastGoodDoorWallPosRef.current = snapResult.position;
                  if (snapResult.rotation) {
                    lastGoodDoorWallRotRef.current = snapResult.rotation;
                  }
                  if (snapResult.wallType) {
                    lastGoodDoorWallIdRef.current = snapResult.wallType;
                  }
                }
              } else if (doorWallLock) {
                const p = lastGoodDoorWallPosRef.current;
                const rq = lastGoodDoorWallRotRef.current;
                commitObjectAfterDrag({
                  id,
                  position: p,
                  rotation: rq,
                  placementType: "wall",
                  snappedToWall: lastGoodDoorWallIdRef.current,
                });
                const snappedRot = new Quaternion(rq[0], rq[1], rq[2], rq[3]);
                matrix.compose(
                  new Vector3(p[0], p[1], p[2]),
                  snappedRot,
                  sclRef.current,
                );
                previousPositionRef.current = p;
              } else {
                // No snap — commit the final position (and rotation for floor objects) once
                const finalPos = previousPositionRef.current;
                const finalRot = isFloorObject
                  ? ([
                      liveRotRef.current.x,
                      liveRotRef.current.y,
                      liveRotRef.current.z,
                      liveRotRef.current.w,
                    ] as [number, number, number, number])
                  : undefined;
                commitObjectAfterDrag({
                  id,
                  position: finalPos,
                  rotation: finalRot,
                });
              }
            }}
          />
        )}

        {shouldShowHandle && isResizable(name) && (
          <ResizeHandles
            id={id}
            position={position}
            rotation={rotation}
            size={typeof size === "number" ? [size, size, size] : size}
            is2D={is2D}
            placementType={placementType}
            onDragStart={() => setIsDraggingResize(true)}
            onDragEnd={() => setIsDraggingResize(false)}
          />
        )}

        <group ref={groupRef}>
          {modelUrl ? (
            // GLB model branch (doors use 2D plan symbols; hide GLB in orthographic top view)
            <>
              {!(is2D && (isDoorObject || isWindowObject)) && (
                <GltfErrorBoundary
                  modelUrl={modelUrl}
                  fallback={
                    <mesh onClick={handleClick}>
                      <boxGeometry
                        args={
                          typeof size === "number"
                            ? [size, size, size]
                            : (size as [number, number, number])
                        }
                      />
                      <meshStandardMaterial
                        color="#ff6b35"
                        transparent
                        opacity={0.6}
                        wireframe
                      />
                    </mesh>
                  }
                >
                  <Suspense
                    fallback={
                      <mesh>
                        <boxGeometry
                          args={
                            typeof size === "number"
                              ? [size, size, size]
                              : (size as [number, number, number])
                          }
                        />
                        <meshStandardMaterial
                          color={color}
                          transparent
                          opacity={0.25}
                          wireframe
                        />
                      </mesh>
                    }
                  >
                    <GltfObject
                      modelUrl={modelUrl}
                      size={
                        typeof size === "number" ? [size, size, size] : size
                      }
                      color={color}
                      is2D={is2D}
                      applyGlassMaterials={isDoorObject}
                      onClick={handleClick}
                    />
                  </Suspense>
                </GltfErrorBoundary>
              )}
              {/* Invisible bounding-box mesh — reliable R3F click target.
                  The GLB scene's child meshes are raw Three.js objects;
                  this explicit R3F <mesh> guarantees the click event fires
                  even if primitive event propagation has timing issues. */}
              <mesh
                onClick={handleClick}
                onPointerDown={() => {
                  objectInteractionFlag.active = true;
                }}
                onPointerUp={() => {
                  objectInteractionFlag.active = false;
                }}
                onPointerLeave={() => {
                  objectInteractionFlag.active = false;
                }}
                visible={false}
                raycast={
                  door2DBlockRaycast
                    ? () => {
                        /* selection from plan swing sector */
                      }
                    : undefined
                }
              >
                {renderGeometry}
              </mesh>
            </>
          ) : (
            // Primitive geometry branch
            <mesh
              castShadow={!is2D}
              receiveShadow={!is2D}
              onClick={handleClick}
              name={name}
            >
              {renderGeometry}
              {is2D ? (
                <meshBasicMaterial color={isSelected ? "#ffaa00" : color} />
              ) : (
                <meshStandardMaterial
                  color={isSelected ? "#ffaa00" : color}
                  emissive={isSelected ? "#ff8800" : "#000000"}
                  emissiveIntensity={isSelected ? 0.3 : 0}
                />
              )}
            </mesh>
          )}

          {/* Group outline - colored wireframe (always visible if in group) */}
          {group && (
            <mesh
              raycast={
                door2DBlockRaycast
                  ? () => {
                      /* 2D door: hit swing overlay */
                    }
                  : undefined
              }
            >
              {renderGeometry}
              <meshBasicMaterial
                color={group.color}
                wireframe
                transparent
                opacity={0.4}
              />
            </mesh>
          )}

          {/* Selection outline - yellow wireframe (only when selected) */}
          {isSelected && (
            <mesh
              raycast={
                door2DBlockRaycast
                  ? () => {
                      /* 2D door: hit swing overlay */
                    }
                  : undefined
              }
            >
              {renderGeometry}
              <meshBasicMaterial
                color="#ffaa00"
                wireframe
                transparent
                opacity={0.6}
              />
            </mesh>
          )}
        </group>
      </group>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison - only re-render if relevant props actually changed
    const prevPos = prevProps.position || [0, 1, 0];
    const nextPos = nextProps.position || [0, 1, 0];
    const prevRot = prevProps.rotation || [0, 0, 0, 1];
    const nextRot = nextProps.rotation || [0, 0, 0, 1];

    return (
      prevProps.id === nextProps.id &&
      prevPos[0] === nextPos[0] &&
      prevPos[1] === nextPos[1] &&
      prevPos[2] === nextPos[2] &&
      prevRot[0] === nextRot[0] &&
      prevRot[1] === nextRot[1] &&
      prevRot[2] === nextRot[2] &&
      prevRot[3] === nextRot[3] &&
      prevProps.color === nextProps.color &&
      prevProps.shape === nextProps.shape &&
      prevProps.modelUrl === nextProps.modelUrl &&
      prevProps.objectRole === nextProps.objectRole &&
      prevProps.snappedToWall === nextProps.snappedToWall &&
      prevProps.collisionLayer === nextProps.collisionLayer &&
      (prevProps.placeOn?.target_instance_id ?? null) ===
        (nextProps.placeOn?.target_instance_id ?? null) &&
      (prevProps.placeOn?.method ?? null) === (nextProps.placeOn?.method ?? null) &&
      JSON.stringify(prevProps.size) === JSON.stringify(nextProps.size)
    );
  },
);

MovableObject.displayName = "MovableObject";

export default MovableObject;
