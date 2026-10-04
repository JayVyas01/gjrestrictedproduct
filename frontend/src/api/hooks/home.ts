import { useQuery } from "@tanstack/react-query";
import { getHome } from "../home";
import { keys, POLL_MS } from "./keys";

export function useHome() {
  return useQuery({ queryKey: keys.home, queryFn: getHome, refetchInterval: POLL_MS });
}
