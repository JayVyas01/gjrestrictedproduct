import "i18next";
import type { defaultNS, resources } from "./index";

// Makes t() keys type-checked against en.json.
declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: typeof defaultNS;
    resources: (typeof resources)["en"];
  }
}
