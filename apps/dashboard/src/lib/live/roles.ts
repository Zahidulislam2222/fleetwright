import type { Session, ViewerRole } from "@/mocks/types";

/** Mirrors the server's ranking (fw_queue.sessions.RANK). The UI only hides what the server refuses anyway. */
const RANK: Record<ViewerRole, number> = { public: 0, viewer: 1, demo: 1, operator: 2, owner: 3 };

export function atLeast(session: Session | null, role: ViewerRole): boolean {
  return session?.authenticated === true && RANK[session.role] >= RANK[role];
}
