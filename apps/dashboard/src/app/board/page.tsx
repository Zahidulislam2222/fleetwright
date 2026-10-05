import type { Metadata } from "next";
import { MockBoard } from "@/components/board/MockBoard";
import copy from "@/content/prototype.json";

export const metadata: Metadata = { title: copy.board.name, robots: { index: false, follow: false } };

export default function BoardPage() {
  return <MockBoard />;
}
