import { rmSync } from "node:fs";
import { resolve } from "node:path";

// Each run starts from a truly fresh vault: no blob, no salt, first-run flow.
export default function globalSetup() {
  rmSync(resolve(import.meta.dirname, "../.e2e-data"), { recursive: true, force: true });
}
