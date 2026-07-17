#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sitemap = fs.readFileSync(path.join(root, "sitemap.xml"), "utf8");
const urls = [...sitemap.matchAll(/<loc>\s*https:\/\/toontones\.net\/([^<]*)<\/loc>/g)].map(
  (match) => match[1],
);
const errors = [];

for (const route of urls) {
  const file = path.join(root, route ? route.replace(/\/$/, "") : "", "index.html");
  const html = fs.readFileSync(file, "utf8");
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];

  scripts.forEach((match, index) => {
    const attrs = match[1];
    const code = match[2];
    if (/\bsrc\s*=/.test(attrs)) return;
    if (/type\s*=\s*["'](?:application\/ld\+json|text\/template)["']/i.test(attrs)) return;
    if (!code.trim()) return;
    try {
      new vm.Script(code, { filename: `${path.relative(root, file)}#script-${index + 1}` });
    } catch (error) {
      errors.push(String(error));
    }
  });
}

if (errors.length) {
  console.error(`FAIL inline-script checks: ${errors.length} issue(s)`);
  errors.forEach((error) => console.error(`- ${error}`));
  process.exit(1);
}

console.log(`PASS inline-script checks: ${urls.length} sitemap pages parsed`);
