export default function SkeletonCard() {
  return (
    <li className="flex flex-col items-center gap-1.5 p-2 rounded-2xl border border-transparent bg-white/70">
      <div className="w-full aspect-square bg-zinc-100 rounded-xl animate-pulse" />
      <div className="w-3/4 h-3 bg-zinc-100 rounded animate-pulse mt-1" />
    </li>
  );
}
