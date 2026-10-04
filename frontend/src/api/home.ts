import { apiGet, type RequestOptions } from "./client";
import type { Home } from "./types";

export function getHome(options?: RequestOptions): Promise<Home> {
  return apiGet<Home>("/api/home", options);
}
