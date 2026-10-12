Fix TypeScript compilation errors in generated test files without changing test logic. Usage: /compile-fix <paste tsc output>

These TypeScript errors appeared after code generation.
Fix all of them. Do not change test logic — only fix type errors.

Errors:
$ARGUMENTS

After fixing, confirm which files were changed and what was corrected in each.

Rules:
- Only fix type errors (wrong types, missing imports, incorrect signatures)
- Do not add, remove, or change any test() blocks or assertions
- Do not change expect() calls or their arguments
- If the same error appears in multiple files, fix all occurrences
- If an error cannot be fixed without changing test logic, flag it for QA review
