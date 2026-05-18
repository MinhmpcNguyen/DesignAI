"use client";

import { useMemo, useEffect, Suspense, Component } from "react";
import type { ReactNode } from "react";
import { RigidBody, CuboidCollider } from "@react-three/rapier";
import { Line, useTexture } from "@react-three/drei";
import { useWalls } from "@/states/slices/walls/hooks";
import {
  useGlobalMaterialId,
  useRoomMaterials,
  useSelectedRoomKey,
  useSetSelectedRoomKey,
} from "@/states/slices/floor/hooks";
import { findRoomPolygons, centroidKey } from "@/lib/roomPolygons";
import { useFloorMaterials } from "@/hooks/useCatalog";
import type { FloorMaterial } from "@/types/global";
import {
  BufferAttribute,
  DoubleSide,
  RepeatWrapping,
  SRGBColorSpace,
  Shape,
  ShapeGeometry,
} from "three";

// ---------------------------------------------------------------------------
// TextureErrorBoundary — catches useTexture() load failures and renders a
// plain color mesh instead of crashing the scene (e.g. CORS errors).
// ---------------------------------------------------------------------------
interface TextureErrorBoundaryProps {
  fallback: ReactNode;
  children: ReactNode;
}

class TextureErrorBoundary extends Component<
  TextureErrorBoundaryProps,
  { hasError: boolean }
> {
  state = { hasError: false };
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(error: Error) {
    console.error("[Floor] TextureErrorBoundary caught texture render error", {
      message: error.message,
      stack: error.stack,
    });
  }
  render() {
    return this.state.hasError ? this.props.fallback : this.props.children;
  }
}

// ---------------------------------------------------------------------------
// RoomFloorTextured — rendered only when material has a textureUrl.
// Isolates useTexture() so its Suspense boundary stays tight per-room.
// ---------------------------------------------------------------------------
function RoomFloorTextured({
  geometry,
  material,
  isSelected,
  onClick,
}: {
  geometry: ShapeGeometry;
  material: FloorMaterial;
  isSelected: boolean;
  onClick: () => void;
}) {
  // Route remote textures through a same-origin API proxy.
  // This avoids browser-side CORS failures when uploading to WebGL.
  const proxiedTextureUrl = useMemo(() => {
    const encoded = encodeURIComponent(material.textureUrl!);
    return `/api/texture-proxy?url=${encoded}`;
  }, [material.textureUrl]);

  const textureMap = useTexture(proxiedTextureUrl);

  // Clone and configure locally so we don't mutate shared hook return value.
  const configuredTexture = useMemo(() => {
    const t = textureMap.clone();
    t.wrapS = RepeatWrapping;
    t.wrapT = RepeatWrapping;
    t.colorSpace = SRGBColorSpace;
    t.needsUpdate = true;
    return t;
  }, [textureMap]);

  useEffect(() => () => configuredTexture.dispose(), [configuredTexture]);

  return (
    <mesh
      rotation={[-Math.PI / 2, 0, 0]}
      receiveShadow
      position={[0, 0.001, 0]}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      <primitive object={geometry} attach="geometry" />
      <meshStandardMaterial
        map={configuredTexture}
        side={DoubleSide}
        emissive="#1a6bff"
        emissiveIntensity={isSelected ? 0.25 : 0}
      />
    </mesh>
  );
}

const FALLBACK_MATERIAL: FloorMaterial = {
  id: "",
  label: "",
  color: "#ded4bd",
  tileSize: 5,
};

// ---------------------------------------------------------------------------
// RoomFloor — chooses textured or color-only path based on material config.
// ---------------------------------------------------------------------------
function RoomFloor({
  polygon,
  materialId,
  floorMaterials,
  isSelected,
  onClick,
}: {
  polygon: [number, number][];
  materialId: string;
  floorMaterials: FloorMaterial[];
  isSelected: boolean;
  onClick: () => void;
}) {
  const material =
    floorMaterials.find((m) => m.id === materialId) ??
    floorMaterials[0] ??
    FALLBACK_MATERIAL;

  const geometry = useMemo(() => {
    const shape = new Shape();
    // Wall [x,z] → shape (x,-z) → after Rx(-π/2) → world (x,0,z)
    shape.moveTo(polygon[0][0], -polygon[0][1]);
    for (let i = 1; i < polygon.length; i++) {
      shape.lineTo(polygon[i][0], -polygon[i][1]);
    }
    shape.closePath();
    const geo = new ShapeGeometry(shape);

    // Bake world-space tiling UVs so texture tiles uniformly regardless of room shape.
    // In shape space: vertex.x = world X, vertex.y = −world Z
    // UV = (worldX / tileSize, worldZ / tileSize) = (x / ts, −y / ts)
    const pos = geo.attributes.position;
    const uvArray = new Float32Array(pos.count * 2);
    const ts = material.tileSize;
    for (let i = 0; i < pos.count; i++) {
      uvArray[i * 2] = pos.getX(i) / ts;
      uvArray[i * 2 + 1] = -pos.getY(i) / ts;
    }
    geo.setAttribute("uv", new BufferAttribute(uvArray, 2));
    return geo;
  }, [polygon, material.tileSize]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  const borderPoints = useMemo<[number, number, number][]>(
    () => [...polygon, polygon[0]].map(([x, z]) => [x, 0.005, z]),
    [polygon],
  );

  if (material.textureUrl) {
    const colorOnlyMesh = (
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        receiveShadow
        position={[0, 0.001, 0]}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
      >
        <primitive object={geometry} attach="geometry" />
        <meshStandardMaterial
          color={material.color}
          side={DoubleSide}
          emissive="#1a6bff"
          emissiveIntensity={isSelected ? 0.25 : 0}
        />
      </mesh>
    );

    return (
      <group>
        <TextureErrorBoundary fallback={colorOnlyMesh}>
          <Suspense fallback={colorOnlyMesh}>
            <RoomFloorTextured
              geometry={geometry}
              material={material}
              isSelected={isSelected}
              onClick={onClick}
            />
          </Suspense>
        </TextureErrorBoundary>
        {isSelected && (
          <Line points={borderPoints} color="#C8A882" lineWidth={2} />
        )}
      </group>
    );
  }

  // Color-only path (no textureUrl)
  return (
    <group>
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        receiveShadow
        position={[0, 0.001, 0]}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
      >
        <primitive object={geometry} attach="geometry" />
        <meshStandardMaterial
          color={material.color}
          side={DoubleSide}
          emissive="#1a6bff"
          emissiveIntensity={isSelected ? 0.25 : 0}
        />
      </mesh>
      {isSelected && (
        <Line points={borderPoints} color="#C8A882" lineWidth={2} />
      )}
    </group>
  );
}

// ---------------------------------------------------------------------------
// Floor — root component; reads Redux and computes per-polygon material ids.
// ---------------------------------------------------------------------------
export default function Floor({
  hideSelection = false,
}: {
  hideSelection?: boolean;
}) {
  const walls = useWalls();
  const globalMaterialId = useGlobalMaterialId();
  const roomMaterials = useRoomMaterials();
  const selectedRoomKey = useSelectedRoomKey();
  const setSelectedRoomKey = useSetSelectedRoomKey();
  const { floorMaterials } = useFloorMaterials();

  const roomPolygons = useMemo(() => findRoomPolygons(walls), [walls]);

  return (
    <>
      {/* Invisible physics collider — always present so objects don't fall through */}
      <RigidBody type="fixed">
        <CuboidCollider
          args={[100, 0.05, 100]}
          position={[0, -0.05, 0]}
          friction={1}
        />
      </RigidBody>

      {roomPolygons.map((polygon, i) => {
        const key = centroidKey(polygon);
        const materialId = roomMaterials[key] ?? globalMaterialId;
        const isSelected = selectedRoomKey === key && !hideSelection;
        return (
          <RoomFloor
            key={key + i}
            polygon={polygon}
            materialId={materialId}
            floorMaterials={floorMaterials}
            isSelected={isSelected}
            onClick={() => setSelectedRoomKey(isSelected ? null : key)}
          />
        );
      })}
    </>
  );
}
