import type { Me, Role } from "@/api/types";

/** Each role's home. A fixed table: never navigate to a path taken from input or the server. */
export const LANDING: Record<Role, string> = {
  LICENSEE: "/licensee",
  PERSONNEL: "/personnel",
  LICENSING_AUTHORITY: "/authority",
  HEAD_AUTHORITY: "/head",
  SOFTWARE_OWNER: "/overview",
};

export function landingFor(role: string): string {
  return role in LANDING ? LANDING[role as Role] : "/";
}

/** Where a session that ended goes: sign-in with the expiry notice. */
export const EXPIRED_PATH = "/sign-in?expired=1";

const DRAFT_PREFIX = "gj.draft.";

function draftKeys(): string[] {
  const drafts: string[] = [];
  for (let i = 0; i < sessionStorage.length; i += 1) {
    const key = sessionStorage.key(i);
    if (key?.startsWith(DRAFT_PREFIX)) drafts.push(key);
  }
  return drafts;
}

/** Is any wizard draft (`gj.draft.*`) saved in this tab? */
export function hasDrafts(): boolean {
  return draftKeys().length > 0;
}

/** Removes every wizard draft (`gj.draft.*`) from sessionStorage; other keys stay. */
export function clearDrafts(): void {
  draftKeys().forEach((key) => sessionStorage.removeItem(key));
}

/**
 * A district position: superintendents review batches and draft rule changes. Only DISTRICT
 * counts, as on the server (oversight and governance services); a state position does not.
 */
export function holdsDistrictPosition(user: Me): boolean {
  return user.positions.some((position) => position.level === "DISTRICT");
}
