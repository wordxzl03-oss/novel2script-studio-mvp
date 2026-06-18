import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const srcRoot = fileURLToPath(new URL("..", import.meta.url));

test("paper/dark tokens avoid banned default AI visual language", () => {
  const css = readFileSync(new URL("./tokens.css", import.meta.url), "utf8");

  assert.match(css, /--paper-bg:/);
  assert.match(css, /--dark-bg:/);
  assert.doesNotMatch(css, /Inter/i);
  assert.doesNotMatch(css, /linear-gradient/i);
  assert.doesNotMatch(css, /#2557d6|#6366f1|#7c3aed/i);
});

test("frontend source does not use local browser storage", () => {
  const files = collectSourceFiles(srcRoot);
  const source = files
    .filter((file) => !file.endsWith(".test.js"))
    .map((file) => readFileSync(file, "utf8"))
    .join("\n");

  assert.doesNotMatch(source, /localStorage|sessionStorage/);
});

function collectSourceFiles(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) {
      return collectSourceFiles(path);
    }
    return path.endsWith(".js") || path.endsWith(".jsx") || path.endsWith(".css")
      ? [path]
      : [];
  });
}
