import { useQuery } from "@tanstack/react-query";
import { getHome } from "../home";
import { isBackground, keys, POLL_MS } from "./keys";

export function useHome() {
  return useQuery({
    queryKey: keys.home,
    queryFn: (context) => getHome({ background: isBackground(context) }),
    refetchInterval: POLL_MS,
  });
}
