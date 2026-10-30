import { access, cp, mkdir } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const standalone = path.join(root, ".next", "standalone");
const staticSource = path.join(root, ".next", "static");
const publicSource = path.join(root, "public");

try {
  await access(path.join(standalone, "server.js"));
} catch {
  throw new Error("Standalone output is missing. Run `npm run build` before `npm run start`.");
}

await mkdir(path.join(standalone, ".next"), { recursive: true });
try {
  await access(staticSource);
  await cp(staticSource, path.join(standalone, ".next", "static"), { recursive: true, force: true });
} catch {
  // A build without static assets is valid; there is nothing to copy.
}
try {
  await access(publicSource);
  await cp(publicSource, path.join(standalone, "public"), { recursive: true, force: true });
} catch {
  // Next.js does not require a public directory to exist.
}
