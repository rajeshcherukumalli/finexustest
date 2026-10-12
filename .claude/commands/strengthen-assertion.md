Upgrade a weak assertion (e.g. status-code only) to check specific response body fields. Usage: /strengthen-assertion <file> <case-id> "<response shape>"

Arguments provided: $ARGUMENTS

Parse the arguments as: <file path> <case id> "<JSON shape of the response body>"

The current test likely only checks the HTTP status code. Strengthen it by:
1. Parsing the response body: const body = await response.json()
2. Adding expect() calls for each field in the response shape:
   - Required string fields: expect(body.field).toBeTruthy()
   - ID fields: expect(typeof body.id).toBe('string') and expect(body.id.length).toBeGreaterThan(0)
   - Status/enum fields: expect(body.status).toBe('EXPECTED_VALUE')
   - Fields that mirror request payload: expect(body.name).toBe(payload.name)
   - Timestamps: expect(new Date(body.createdAt).getTime()).not.toBeNaN()
   - Avoid asserting: auto-increment IDs, exact timestamps, server-generated tokens

Do not change the HTTP status assertion.
Do not change any other test in the file.
Show a diff of what was added.
