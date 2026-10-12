Fill fixture placeholder stubs with realistic domain-appropriate test data. Usage: /fixture-fill <module> <FLOW-ID>

Read tests/scripts/fixtures/{module}/{FLOW-ID}.fixtures.ts (just written by /script-gen).
Read agents/domain-rules/{project}.rules.ts for data constraints.

Fill every placeholder in the fixtures file with realistic values.

Rules per case type:
  happy_path:             valid data matching domain rules
  edge_case duplicate:    same ID/phone as a pre-seeded record (reference seed script)
  edge_case expired:      timestamps set to past (use rules.dateFormat)
  edge_case oversized:    file size = rules.oversizedBytes
  edge_case missing:      omit the field marked required in the API endpoint
  rbac_check:             use actor credentials with insufficient permissions

All seeded records: prefix name/key with ${rules.seedPrefix}-${Date.now()}

Use realistic values — not 'test123' or 'foo'. Use:
  - Real-looking names from the project locale (rules.locale)
  - Valid phone numbers in the correct format
  - Future dates for scheduling, past dates for historical records
  - Valid file extensions from rules.validFileTypes
  - rules.otpValue for OTP fields in QA environment

Export as: export const fixtures = { ... } as const;

Overwrite the existing fixture stub file.
