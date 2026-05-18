"use client";

import React, { useState } from "react";
import {
  ChevronUp,
  ChevronDown,
  GripVertical,
  Edit2,
  Trash2,
  Check,
  X,
} from "lucide-react";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import {
  useGroupsValue,
  useUngroup,
  useRenameGroup,
} from "@/states/slices/groups/hooks";
import { useObjectsValue } from "@/states/slices/objects/hooks";
import type { Group } from "@/states/slices/groups/types";

// ---------------------------------------------------------------------------
// GroupAccordionTrigger — custom trigger row for a group
// ---------------------------------------------------------------------------

interface GroupAccordionTriggerProps {
  group: Group;
  isRenaming: boolean;
  renameDraft: string;
  onRenameDraftChange: (v: string) => void;
  onRenameSave: () => void;
  onRenameCancel: () => void;
  onStartRename: () => void;
  onUngroup: () => void;
}

function GroupAccordionTrigger({
  group,
  isRenaming,
  renameDraft,
  onRenameDraftChange,
  onRenameSave,
  onRenameCancel,
  onStartRename,
  onUngroup,
}: GroupAccordionTriggerProps) {
  if (isRenaming) {
    // Replace the trigger entirely with a flat input row — no nested buttons
    return (
      <div className="flex items-center gap-1 px-2 py-2">
        <span className="flex shrink-0 text-zinc-300">
          <GripVertical size={13} />
        </span>
        <input
          type="text"
          value={renameDraft}
          autoFocus
          onChange={(e) => onRenameDraftChange(e.target.value)}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === "Enter") onRenameSave();
            if (e.key === "Escape") onRenameCancel();
          }}
          className="flex-1 min-w-0 px-1 py-0.5 text-xs bg-white border border-zinc-300 rounded outline-none focus:border-(--primary-color)"
        />
        <button
          type="button"
          onClick={onRenameSave}
          className="p-0.5 rounded text-green-600 hover:bg-green-50 transition-colors"
          aria-label="Lưu"
        >
          <Check size={11} />
        </button>
        <button
          type="button"
          onClick={onRenameCancel}
          className="p-0.5 rounded text-zinc-400 hover:bg-zinc-100 transition-colors"
          aria-label="Hủy"
        >
          <X size={11} />
        </button>
      </div>
    );
  }

  // Normal state: AccordionTrigger (chevron + grip + name) with "..." menu as a sibling
  // GroupMenuDropdown is placed OUTSIDE the trigger button to avoid nested <button>
  return (
    <div className="flex items-center">
      <AccordionTrigger className="flex-1 items-center justify-start gap-1.5 px-2 py-2 text-xs font-medium text-zinc-700 hover:bg-zinc-50 hover:no-underline rounded-md">
        {/* Grip handle — inside a span so it is not a direct SVG child and won't rotate */}
        <span className="flex shrink-0 text-zinc-300">
          <GripVertical size={13} />
        </span>
        <span className="flex-1 truncate text-[11px] font-semibold text-zinc-700">
          {group.name}{" "}
          <span className="font-normal text-zinc-400">(group)</span>
        </span>
      </AccordionTrigger>
      {/* Action buttons — siblings of the trigger, never nested inside <button> */}
      <div className="flex items-center gap-0.5 pr-1 shrink-0">
        <button
          type="button"
          onClick={onStartRename}
          className="p-1 rounded text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
          aria-label="Đổi tên nhóm"
        >
          <Edit2 size={12} />
        </button>
        <button
          type="button"
          onClick={onUngroup}
          className="p-1 rounded text-zinc-400 hover:text-red-500 hover:bg-red-50 transition-colors"
          aria-label="Giải nhóm"
        >
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// GroupOverlay — main component
// ---------------------------------------------------------------------------

export default function GroupOverlay() {
  const { groups } = useGroupsValue();
  const { objects } = useObjectsValue();
  const ungroup = useUngroup();
  const renameGroup = useRenameGroup();

  const [collapsed, setCollapsed] = useState(false);
  const [renamingGroupId, setRenamingGroupId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");

  // Build a fast objectId → name lookup
  const objectNameMap = React.useMemo(() => {
    const map: Record<string, string> = {};
    objects.forEach((obj) => {
      map[obj.id] = obj.name ?? "Tên đồ vật";
    });
    return map;
  }, [objects]);

  const startRename = (group: Group) => {
    setRenamingGroupId(group.id);
    setRenameDraft(group.name);
  };

  const saveRename = () => {
    if (renamingGroupId && renameDraft.trim()) {
      renameGroup({ groupId: renamingGroupId, newName: renameDraft.trim() });
    }
    setRenamingGroupId(null);
    setRenameDraft("");
  };

  const cancelRename = () => {
    setRenamingGroupId(null);
    setRenameDraft("");
  };

  if (groups.length === 0) return null;

  return (
    <div
      className="bg-white rounded-xl shadow-(--shadow-style) overflow-hidden"
      style={{ border: "var(--border-style)", width: "16rem" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-100">
        <span className="text-xs font-semibold text-zinc-700 select-none">
          Layer
        </span>
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className="p-1 rounded text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
          aria-label={collapsed ? "Mở rộng" : "Thu gọn"}
        >
          {collapsed ? <ChevronDown size={13} /> : <ChevronUp size={13} />}
        </button>
      </div>

      {/* Accordion body */}
      {!collapsed && (
        <div className="max-h-80 overflow-y-auto py-1">
          <Accordion type="multiple" className="w-full">
            {groups.map((group) => {
              const isRenaming = renamingGroupId === group.id;
              return (
                <AccordionItem
                  key={group.id}
                  value={group.id}
                  className="border-b border-zinc-100 last:border-b-0 px-1"
                >
                  <GroupAccordionTrigger
                    group={group}
                    isRenaming={isRenaming}
                    renameDraft={renameDraft}
                    onRenameDraftChange={setRenameDraft}
                    onRenameSave={saveRename}
                    onRenameCancel={cancelRename}
                    onStartRename={() => startRename(group)}
                    onUngroup={() => ungroup(group.id)}
                  />
                  <AccordionContent className="pb-1">
                    <ul className="space-y-0.5 pl-1">
                      {group.objectIds.map((objId) => (
                        <li
                          key={objId}
                          className="flex items-center gap-1.5 px-2 py-1 rounded text-[11px] text-zinc-600 hover:bg-zinc-50 transition-colors"
                        >
                          <GripVertical
                            size={11}
                            className="shrink-0 text-zinc-300"
                          />
                          <span className="truncate">
                            {objectNameMap[objId] ?? "Tên đồ vật"}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        </div>
      )}
    </div>
  );
}
