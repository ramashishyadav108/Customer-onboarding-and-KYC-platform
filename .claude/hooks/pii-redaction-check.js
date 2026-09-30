#!/usr/bin/env node
'use strict';
// NFR-03: block logging of plaintext PII in backend source.
const fs = require('fs');

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const ti = input.tool_input || {};
  const filePath = (ti.file_path || '').replace(/\\/g, '/');
  if (!/backend\/src\/.*\.py$/.test(filePath) || /redaction\.py$/.test(filePath)) process.exit(0);

  const text = ti.content || ti.new_string || '';
  const logCall = /(logger|logging|log)\.(debug|info|warning|warn|error|exception|critical)\(|\bprint\(/;
  const pii = /\b(pan|aadhaar|aadhar|phone|mobile|email|contact|annual_income|income|occupation|date_of_birth|dob|full_name|prospect_name)\b/i;
  const bad = text.split('\n').filter((l) => logCall.test(l) && pii.test(l) && !/redact/i.test(l));

  if (bad.length) {
    process.stdout.write(
      `BLOCKED (NFR-03): possible plaintext PII in log call in ${filePath}:\n${bad.slice(0, 3).join('\n')}\n` +
      'Fix: log case_id only, or pass values through config/redaction.redact().\n'
    );
    process.exit(2);
  }
} catch (_) {
  // Silent exit: stderr output triggers a "hook error" in Claude Code
}

process.exit(0);
