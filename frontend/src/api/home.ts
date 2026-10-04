import { apiGet } from "./client";
import type { Home } from "./types";

export function getHome(): Promise<Home> {
  return apiGet<Home>("/api/home");
}
