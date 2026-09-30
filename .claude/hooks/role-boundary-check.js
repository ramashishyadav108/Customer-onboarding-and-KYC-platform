#!/usr/bin/env node
'use strict';
// NFR-04: every non-public route in controllers declares a role guard; no HTTP/auth logic in services.
const fs = require('fs');

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const ti = input.tool_input || {};
  const filePath = (ti.file_path || '').replace(/\\/g, '/');
  const text = ti.content || ti.new_string || '';

  if (/backend\/src\/services\/.*\.py$/.test(filePath) && /(Depends\(|HTTPException|require_role|\bRequest\b)/.test(text)) {
    process.stdout.write(
      `BLOCKED (NFR-04): ${filePath} contains HTTP/auth concerns. The authentication boundary is the controller layer.\n`
    );
    process.exit(2);
  }

  if (/backend\/src\/controllers\/routers\/.*\.py$/.test(filePath) && !/health|leads/.test(filePath) && ti.content) {
    const routes = (ti.content.match(/@router\.(get|post|put|patch|delete)\(/g) || []).length;
    const guarded = (ti.content.match(/require_role\(/g) || []).length;
    if (routes > guarded) {
      process.stdout.write(
        `BLOCKED (NFR-04): ${filePath} has ${routes} routes but only ${guarded} role guards. ` +
        'Add require_role(...) to every non-public route (POST /leads and /health are the only public routes).\n'
      );
      process.exit(2);
    }
  }
} catch (_) {
  // Silent exit
}

process.exit(0);
