"use client";

import { DndContext, PointerSensor, useDroppable, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, rectSortingStrategy, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { motion } from "framer-motion";
import { CalendarClock } from "lucide-react";

import Card, { CardTitle } from "@/components/premium/ui/Card";
import Badge from "@/components/premium/ui/Badge";
import { cn } from "@/lib/utils";

const laneOrder = ["Saved", "Applied", "Interview", "Offer", "Archived"];

function findLaneForId(board, id) {
  const value = String(id);
  if (laneOrder.includes(value)) return value;
  return laneOrder.find((lane) => (board[lane] || []).some((item) => String(item.id) === value)) || null;
}

export default function ApplicationBoard({ board, onMove, disabled = false }) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));
  const allIds = Object.values(board).flat().map((x) => x.id);

  function handleDragEnd(event) {
    if (disabled || !onMove) return;
    const { active, over } = event;
    if (!active?.id || !over?.id) return;
    const sourceLane = findLaneForId(board, active.id);
    const targetLane = findLaneForId(board, over.id);
    if (!sourceLane || !targetLane || sourceLane === targetLane) return;
    onMove(String(active.id), sourceLane, targetLane);
  }

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <SortableContext items={allIds} strategy={rectSortingStrategy}>
        <div className="grid gap-3 xl:grid-cols-5">
          {laneOrder.map((lane) => (
            <LaneColumn key={lane} lane={lane} items={board[lane] || []} disabled={disabled} />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}

function LaneColumn({ lane, items, disabled }) {
  const { setNodeRef, isOver } = useDroppable({ id: lane, disabled });
  return (
    <div ref={setNodeRef}>
      <Card className={cn("p-3 transition-colors", isOver && "border-primary bg-primary/5")}>
        <CardTitle className="mb-3 text-sm uppercase tracking-wide text-muted">{lane}</CardTitle>
        <div className="space-y-2">
          {items.map((item) => (
            <SortableCard key={item.id} item={item} />
          ))}
          {items.length === 0 ? (
            <div className="rounded-md border border-dashed border-border px-2 py-4 text-center text-xs text-muted">
              Drop here
            </div>
          ) : null}
        </div>
      </Card>
    </div>
  );
}

function SortableCard({ item }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id });
  const style = { transform: CSS.Transform.toString(transform), transition };
  return (
    <motion.div ref={setNodeRef} style={style} {...attributes} {...listeners} layout className={cn("cursor-grab rounded-md border border-border bg-card p-2 text-sm shadow-sm", isDragging && "opacity-70")}>
      <p className="font-medium">{item.title}</p>
      <p className="text-xs text-muted">{item.company}</p>
      <p className="mt-1 text-xs text-muted">Resume: {item.resume}</p>
      <div className="mt-2 flex items-center gap-1 text-xs text-muted">
        <CalendarClock className="h-3 w-3" /> {item.date}
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {(item.tags || []).map((tag) => (
          <Badge key={tag} tone="info">
            {tag}
          </Badge>
        ))}
      </div>
    </motion.div>
  );
}
