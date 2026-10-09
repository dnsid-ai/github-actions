import assert from "node:assert/strict";
import { test } from "node:test";
import { checksum } from "./checksum.ts";

test("checksum", () => {
  assert.equal(checksum("abc"), "900150983cd24fb0d6963f7d28e17f72");
});
