import { useCallback, useEffect } from "react";
import { RedoIcon, UndoIcon } from "../icons";
import VerticalDivide from "../VerticalDivide";
import { useAppDispatch, useAppSelector } from "@/states/reduxHooks";
import {
  appUndo,
  appRedo,
  selectCanUndo,
  selectCanRedo,
} from "@/states/undoRedo";

export default function UndoRedoControls() {
  const dispatch = useAppDispatch();
  const canUndo = useAppSelector(selectCanUndo);
  const canRedo = useAppSelector(selectCanRedo);

  const handleUndo = useCallback(() => {
    dispatch(appUndo());
  }, [dispatch]);

  const handleRedo = useCallback(() => {
    dispatch(appRedo());
  }, [dispatch]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return;

      const target = event.target as HTMLElement | null;
      const isTypingElement =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target?.isContentEditable;
      if (isTypingElement) return;

      // Ctrl+Z — undo
      if (event.key.toLowerCase() === "z" && !event.shiftKey) {
        event.preventDefault();
        handleUndo();
        return;
      }

      // Ctrl+Y or Ctrl+Shift+Z — redo
      if (
        event.key.toLowerCase() === "y" ||
        (event.key.toLowerCase() === "z" && event.shiftKey)
      ) {
        event.preventDefault();
        handleRedo();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleUndo, handleRedo]);

  return (
    <div
      className="flex bg-white items-center p-4 rounded-xl shadow-(--shadow-style)"
      style={{ border: "var(--border-style)" }}
    >
      <button
        type="button"
        aria-label="Undo"
        title="Hoàn tác (Ctrl+Z)"
        disabled={!canUndo}
        className="flex items-center justify-center cursor-pointer active:scale-95 active:opacity-80 transition-transform focus:outline-none disabled:opacity-30 disabled:cursor-not-allowed disabled:scale-100"
        onClick={handleUndo}
      >
        <UndoIcon />
      </button>
      <VerticalDivide />
      <button
        type="button"
        aria-label="Redo"
        title="Làm lại (Ctrl+Y)"
        disabled={!canRedo}
        className="flex items-center justify-center cursor-pointer active:scale-95 active:opacity-80 transition-transform focus:outline-none disabled:opacity-30 disabled:cursor-not-allowed disabled:scale-100"
        onClick={handleRedo}
      >
        <RedoIcon />
      </button>
    </div>
  );
}
