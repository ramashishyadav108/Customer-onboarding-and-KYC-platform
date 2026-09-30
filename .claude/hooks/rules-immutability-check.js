#!/usr/bin/env node
'use strict';
// NFR-02 / NFR-05 / NFR-08: block edits that mutate published rules, append-only tables or existing migrations.
const fs = require('fs');

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const ti = input.tool_input || {};
  const filePath = (ti.file_path || '').replace(/\\/g, '/');
  const tool = input.tool_name || '';

  const isMigration = /backend\/migrations\/versions\/.*\.py$/.test(filePath);
  // Editing an EXISTING migration is forbidden; writing a new migration file is fine.
  if (isMigration && tool === 'Edit') {
    process.stdout.write(
      `BLOCKED (NFR-05): ${filePath} is an existing migration. Migrations are append-only; add a new migration instead.\n`
    );
    process.exit(2);
  }

  if (!/backend\/src\/(repositories|services)\/.*\.py$/.test(filePath)) process.exit(0);

  const text = ti.content || ti.new_string || '';
  const tables = /(document|screening_result|decision|override|state_history|audit|watchlist|rule_set|rule_version)/i;
  const bad = text
    .split('\n')
    .filter((l) => /\b(UPDATE|DELETE\s+FROM)\b|\.delete\(|\.update\(/.test(l) && tables.test(l));

  if (bad.length) {
    process.stdout.write(
      `BLOCKED (NFR-02/NFR-08): mutation of an append-only or published-rule table in ${filePath}:\n${bad.slice(0, 3).join('\n')}\n` +
      'Fix: append a new row or a new rule version instead.\n'
    );
    process.exit(2);
  }
} catch (_) {
  // Silent exit
}

process.exit(0);
