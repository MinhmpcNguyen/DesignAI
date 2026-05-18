# Performance Test Guide

This guide covers how to verify the two high-severity performance fixes and monitor
ongoing performance in this project. The app uses `frameloop="demand"` (R3F only
renders on interaction), so raw FPS is not a meaningful idle metric. Use the
method that matches what you want to measure.

---

## Fix 1 — MovableObject Re-render Count

**What was fixed:** `useSelectionValue()` subscribed every `MovableObject` to the
entire selection state. Every Ctrl press or click caused all N objects to re-render.
Now each object subscribes only to its own selected state via granular selectors.

### Method A — Temporary render counter (fastest, no tools needed)

Add this block at the top of the `MovableObject` function body
(`src/components/object-handler/MovableObject.tsx`):

```ts
const renderCount = useRef(0);
if (process.env.NODE_ENV === "development") {
  renderCount.current++;
  console.log(`[MO] ${id.slice(-6)} render ×${renderCount.current}`);
}
```

**Test steps:**

1. Start the dev server (`npm run dev`)
2. Open the browser console, filter by `[MO]`
3. Place 5 objects in the scene
4. Ctrl+click between 3 different objects

**Expected BEFORE fix:** ~5 lines per click (one per object, all re-rendering).  
**Expected AFTER fix:** 1–2 lines per click (only the newly selected + deselected objects).

Remove the block when done.

---

### Method B — React DevTools Profiler (visual, no code change)

**Requirements:** Install the [React DevTools](https://react.dev/learn/react-developer-tools) browser extension.

**Test steps:**

1. Open DevTools → **Profiler** tab
2. Click the ⚙ gear icon → enable **"Record why each component rendered"**
3. Click **Start profiling** (the record button)
4. Place 5 objects, then Ctrl+click between them several times
5. Stop profiling

**Reading the results:**

- In the flame chart, each bar is one component render
- Click a `MovableObject` bar to see **"Why did this render?"** in the right panel
- **BEFORE fix:** clicking one object shows all `MovableObject` instances in the chart
  because `useSelectionValue` returned a new object reference on every dispatch
- **AFTER fix:** only 1–2 `MovableObject` bars appear per click; the rest are greyed
  out (skipped)

---

## Fix 2 — Wall Material GPU Memory Leak

**What was fixed:** `new THREE.MeshStandardMaterial()` × 6 was called inside
`.map()` on every render, with no `.dispose()`. Now materials are created once
per wall inside `useMemo` and disposed in a `useEffect` cleanup.

### Method A — Chrome Memory Heap Snapshot

**Test steps:**

1. Open Chrome DevTools → **Memory** tab
2. Select **Heap snapshot**, click **Take snapshot** → label it `baseline`
3. In the app, draw 4 walls
4. Perform an action that triggers re-renders: pan the camera, select/deselect
   an object, or drag a wall endpoint (anything that forces a React render)
5. Repeat step 4 about 10 times
6. Take another snapshot → label it `after-renders`
7. In the `after-renders` snapshot, type `MeshStandardMaterial` in the filter box

**Reading the results:**

- **BEFORE fix:** the `Count` column grows with each render cycle. With 4 walls
  × 6 materials × 10 renders = up to 240 leaked `MeshStandardMaterial` objects
- **AFTER fix:** the `Count` stays at `8` (2 unique materials per wall × 4 walls),
  regardless of how many renders occurred

---

### Method B — Chrome Performance Timeline

**Test steps:**

1. DevTools → **Performance** tab → click **Record**
2. Drag a wall endpoint slowly for 3–4 seconds to generate many re-renders
3. Stop recording

**Reading the results:**

- Look at the **JS Heap** line at the top of the timeline
- **BEFORE fix:** the heap climbs steadily during the drag (sawtooth pattern where
  even the valleys are higher than the start), indicating accumulating material objects
  waiting for GC
- **AFTER fix:** the heap stays flat during the drag; the `useMemo` materials are
  reused and nothing accumulates

---

## General Drag Performance (Frame Time)

This applies to both fixes and measures the cost per frame during a drag.

**Test steps:**

1. DevTools → **Performance** tab → Record
2. Drag a placed furniture object quickly in a large arc for 3 seconds
3. Stop recording

**What to look at:**

- In the **Main** thread lane, zoom into the scripting blocks for individual frames
- A healthy frame (at 60 FPS target) has < 16ms total work
- Look for **"Minor GC"** purple blocks — frequent minor GCs indicate per-frame
  allocations leaking into the old generation (the `Vector2`/`Vector3` issue noted
  in the audit)

---

## Quick Reference

| What to verify            | Best method                         | Time needed |
| ------------------------- | ----------------------------------- | ----------- |
| Re-render count reduced   | Temporary render counter (Method A) | 2 min       |
| Re-render visual proof    | React DevTools Profiler (Method B)  | 5 min       |
| Material leak stopped     | Heap snapshot (Method A)            | 5 min       |
| Memory growth during drag | Performance timeline (Method B)     | 5 min       |
| Per-frame JS cost         | Performance timeline                | 5 min       |

---

## Notes Specific to This Project

- **`frameloop="demand"`** — R3F only renders when `invalidate()` is called.
  FPS at idle is 0; this is correct, not a bug. Measure FPS only while actively
  dragging or moving the camera.
- **Redux `serializableCheck: false`** — the store has this disabled intentionally
  because `selectedIds` is a `Set`. This means Redux DevTools may show serialization
  warnings; ignore them during performance testing.
- **React Strict Mode** — Next.js dev mode double-invokes effects. When counting
  renders with the counter above, divide by 2 if numbers seem doubled, or disable
  Strict Mode temporarily in `next.config.ts` (`reactStrictMode: false`).
