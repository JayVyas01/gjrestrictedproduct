import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { csvRow } from "./demo-data";

const REPO = fileURLToPath(new URL("../..", import.meta.url));

// The specs read demo-data/parties.csv for parties without a persona (their GSTIN and password)
// and to check sign-up and password changes reach the CSV files. The seed writes them last.
const SANAND_RETAIL_GSTIN = "99AAHCS4004D1Z8";

export default function globalSetup(): void {
  if (process.env.E2E_SKIP_RESET !== "1") {
    // Recreates the database from scratch and seeds the demo story (about 20 seconds, offline).
    // Every official's issued password is back, so each one's first sign-in in this run goes
    // through the change-password page (helpers.ts).
    process.stdout.write("e2e: make demo-reset\n");
    execFileSync("make", ["demo-reset"], {
      cwd: REPO,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "inherit"],
    });
  }
  if (!csvRow("parties.csv", "gstin", SANAND_RETAIL_GSTIN)) {
    throw new Error("e2e: demo-data/parties.csv has no Sanand Retail Wines row; was it seeded?");
  }
}
