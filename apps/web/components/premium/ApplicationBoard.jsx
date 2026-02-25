"use client";

import { DndContext, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, rectSortingStrategy, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { motion } from "framer-motion";
import { CalendarClock } from "lucide-react";

import Card, { CardTitle } from "@/components/premium/ui/Card";
import Badge from "@/components/premium/ui/Badge";
import { cn } from "@/lib/utils";

const laneOrder = ["Saved", "Applied", "Interview", "Offer", "Archived"];

export default function ApplicationBoard({ board }) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));
  const allIds = Object.values(board).flat().map((x) => x.id);

  return (
    <DndContext sensors={sensors}>
      <SortableContext items={allIds} strategy={rectSortingStrategy}>
        <div className="grid gap-3 xl:grid-cols-5">
          {laneOrder.map((lane) => (
            <Card key={lane} className="p-3">
              <CardTitle className="mb-3 text-sm uppercase tracking-wide text-muted">{lane}</CardTitle>
              <div className="space-y-2">
                {(board[lane] || []).map((item) => (
                  <SortableCard key={item.id} item={item} />
                ))}
              </div>
            </Card>
          ))}
        </div>
      </SortableContext>
    </DndContext>
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
