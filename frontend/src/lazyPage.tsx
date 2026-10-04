import { lazy, Suspense, type ComponentType } from "react";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";

/**
 * A route page whose code loads on first visit (its own chunk, so the first download stays
 * small). Until it arrives the page area shows the loading skeleton; the shell stays put.
 * `load` resolves to the page component, e.g.
 * `lazyPage(() => import("@/features/batches/BatchPage").then((m) => m.BatchPage))`.
 */
export function lazyPage<P extends object>(load: () => Promise<ComponentType<P>>): ComponentType<P> {
  // React's lazy types can't carry a generic P through to JSX; the component is P's own.
  const Lazy = lazy(async () => ({ default: await load() })) as unknown as ComponentType<P>;
  function LazyPage(props: P) {
    return (
      <Suspense fallback={<LoadingSkeleton lines={5} />}>
        <Lazy {...props} />
      </Suspense>
    );
  }
  return LazyPage;
}
