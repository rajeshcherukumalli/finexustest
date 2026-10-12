Run an overlap analysis before generating YAML for a new module. Usage: /overlap-analysis <module>

Read all existing YAML files in tests/testcases/ recursively.
Also read the new test plan at tests/testplan/$ARGUMENTS.md.

Produce an overlap report with three sections:

1. EXACT DUPLICATES
   List any test cases in the new plan that are identical to
   existing YAML cases (same endpoint + same assertion).

2. OVERLAPPING COVERAGE
   List endpoints in the new plan already covered in existing YAML.
   Note which existing flow covers them and what scenario.

3. REDUNDANT EDGE CASES
   List edge cases (401, 403, bad payload) in the new plan
   already covered in tests/testcases/_shared/.

For each item, state: should this be removed, consolidated,
or kept because it covers a genuinely different scenario?

Do not generate any YAML. Only produce the report.
