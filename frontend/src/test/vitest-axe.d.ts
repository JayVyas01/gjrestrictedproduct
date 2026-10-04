// vitest-axe 0.1.0 only augments the legacy global `Vi` namespace; current Vitest reads
// matcher types from the `vitest` module, so declare `toHaveNoViolations` there.
import type { AxeMatchers } from "vitest-axe/matchers";

declare module "vitest" {
  // The type parameter must match Vitest's own declaration, even though it is unused here.
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type, @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars
  interface Assertion<T = any> extends AxeMatchers {}
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface AsymmetricMatchersContaining extends AxeMatchers {}
}
