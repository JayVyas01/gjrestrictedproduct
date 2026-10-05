import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const REPO = fileURLToPath(new URL("../..", import.meta.url));
const COMPOSE = ["compose", "--env-file", ".env.demo", "-f", "docker-compose.demo.yml"];

// The two-step journey needs a buyer whose licence takes 250 L of Whisky in one sale. The buyer
// persona (a hotel permit room, 200 L a sale) cannot, so the test signs in as Sanand Retail Wines,
// a seeded Licensee without a persona. Its user ID is random per seed: read it from the backend
// container (SYSTEM read; the test harness only, never the app).
const RETAIL_USER_ID = `
from core.db_context import acting_as_system
from identity.models import User
from licensing.service import find_by_number
with acting_as_system("e2e_lookup"):
    licence = find_by_number("DEMO/AHD/0005")
    print("USER_ID=" + User.objects.get(licensee_gstin_index=licence.gstin_index).user_id)
`;

function run(command: string, args: string[]): string {
  return execFileSync(command, args, {
    cwd: REPO,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "inherit"],
  });
}

export default function globalSetup(): void {
  if (process.env.E2E_SKIP_RESET !== "1") {
    // Recreates the database from scratch and seeds the demo story (about 20 seconds, offline).
    process.stdout.write("e2e: make demo-reset\n");
    run("make", ["demo-reset"]);
  }
  const shell = ["exec", "-T", "backend", "python", "manage.py", "shell", "-c", RETAIL_USER_ID];
  const output = run("docker", [...COMPOSE, ...shell]);
  const userId = /USER_ID=(GJ[A-Z0-9]+)/.exec(output)?.[1];
  if (!userId) throw new Error("e2e: could not read the Sanand Retail Wines user ID");
  // Workers inherit the environment set here.
  process.env.E2E_RETAIL_USER_ID = userId;
}
