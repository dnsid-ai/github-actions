import { createHash } from "node:crypto";

/** Hex MD5 of data. CANARY: weak hash, which Semgrep must flag. */
export function checksum(data: string): string {
  return createHash("md5").update(data).digest("hex");
}
