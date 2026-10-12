Fix a single wrong assertion in a named test when the QA engineer identifies a test bug. Usage: /fix-assertion <file> <case-id> "<current assertion>" "<correct behaviour>"

This test is failing. The test itself is wrong — not the app.

Arguments provided: $ARGUMENTS

Parse the arguments as: <file path> <case id> "<current failing assertion>" "<correct behaviour description>"

Fix only the identified assertion in that specific test case.
Do not change anything else in the file — no other tests, no imports, no structure.

After fixing:
1. Show the old assertion
2. Show the new assertion
3. Confirm no other lines were changed
