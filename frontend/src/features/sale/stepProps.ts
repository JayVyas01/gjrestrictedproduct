import type { SaleDraft } from "./draft";
import type { FieldErrors } from "./validation";

/** What every wizard step gets from NewSalePage. */
export interface StepProps {
  draft: SaleDraft;
  /** Changes the draft (saved to sessionStorage after a pause). */
  update: (patch: Partial<SaleDraft>) => void;
  errors: FieldErrors;
  /** Sets or clears (undefined) the messages under some fields. */
  setErrors: (patch: FieldErrors) => void;
}
