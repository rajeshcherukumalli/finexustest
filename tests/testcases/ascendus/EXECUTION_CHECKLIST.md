# Ascendus Loan Application - Test Execution Checklist

## Pre-Execution Setup

### Environment & Dependencies
- [ ] Approved QA URLs available: Portal and LOS
- [ ] Build/version confirmed and ready
- [ ] Fresh QA email mailbox provisioned and tested
- [ ] Email OTP delivery confirmed working
- [ ] Plaid sandbox configured with approved test institution
- [ ] Plaid test credentials valid: `{{PLAID_SANDBOX_ID}}` / `{{PLAID_SANDBOX_CODE}}`
- [ ] LOS ADMIN account credentials confirmed
- [ ] LOS restricted-role account created for access isolation tests
- [ ] Address lookup provider (Geocoding API) accessible
- [ ] Address provider timeout simulation available
- [ ] All .env variables populated (see test_data_fixtures.yaml)

### Data Provisioning
- [ ] TD01 identity fixtures confirmed unique and approved
- [ ] TD02 boundary test data prepared (min/max amounts)
- [ ] TD03 expired OTP code available (>15 min old)
- [ ] TD03 wrong code fixture ready
- [ ] TD04 multi-purpose and conditional logic data prepared
- [ ] TD05 approved bank statement file prepared (PDF, <5MB)
- [ ] TD05 invalid files prepared (oversized, corrupt, wrong format)
- [ ] TD06 ECDUP01 error fixture documented and ready
- [ ] TD06 duplicate submission simulation method confirmed
- [ ] TD07 second applicant session capability available
- [ ] All approved EINs and SSNs confirmed unique
- [ ] Plaid sandbox account with correct institution type

### Business Rules Approval Status
- [ ] Q01: Field validation and boundary rules ✓ / ⧗ / ✗
- [ ] Q02: Email OTP expiry and resend policy ✓ / ⧗ / ✗
- [ ] Q03: Referral source dependencies ✓ / ⧗ / ✗
- [ ] Q04: Address/business validation rules ✓ / ⧗ / ✗
- [ ] Q05: Identity and citizenship restrictions ✓ / ⧗ / ✗
- [ ] Q06: Consent and submission idempotency ✓ / ⧗ / ✗
- [ ] Q07: ECDUP01 duplicate detection logic ✓ / ⧗ / ✗
- [ ] Q08: Ownership percentage and address logic ✓ / ⧗ / ✗
- [ ] Q09: Multi-purpose amount calculation ✓ / ⧗ / ✗
- [ ] Q10: Income annualization formula ✓ / ⧗ / ✗
- [ ] Q11: Household and employment validation ✓ / ⧗ / ✗
- [ ] Q12: Demographics and credit impact mapping ✓ / ⧗ / ✗
- [ ] Q13: Reference requirements and skip rules ✓ / ⧗ / ✗
- [ ] Q14: Manual statement upload as Plaid alternative ✓ / ⧗ / ✗
- [ ] Q15: Plaid integration and account selection ✓ / ⧗ / ✗
- [ ] Q17: Back-navigation and completion tracking ✓ / ⧗ / ✗
- [ ] Q18: Authentication and data isolation rules ✓ / ⧗ / ✗
- [ ] Q19: Performance SLAs and duplicate prevention ✓ / ⧗ / ✗

**Legend**: ✓ = Approved, ⧗ = Pending, ✗ = Rejected/Blocked

### Entry Criteria Verification
- [ ] Paired QA environments and builds available
- [ ] OTP, address/identity, and Plaid sandbox dependencies working
- [ ] TD01 freshly provisioned with unique identifiers
- [ ] Negative test fixtures ready (selected scenarios)
- [ ] Restricted test roles created and accessible
- [ ] All blocking Q-decisions have approved answers
- [ ] Tests explicitly marked Blocked for any unanswered Q-decisions

---

## Phase Execution

### Phase 1: Smoke Test (P1 - Critical Path)

**Test Cases**: TP01
**Data Profile**: TD01
**Estimated Duration**: 15-20 minutes per run
**Entry Criteria**: All dependencies verified above

- [ ] **TP01-1**: Open portal with fresh QA credentials
  - Expected: Application entry controls visible
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked

- [ ] **TP01-2**: Start application (Amount $25k, GA, email, agreement)
  - Expected: First OTP modal for correct mailbox
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked

- [ ] **TP01-3**: Verify first email OTP
  - Expected: Details stage opens
  - Generated OTP: ________________  Date: _______  Result: ✓ / ✗ / Blocked

- [ ] **TP01-4**: Enter applicant & referral (TD01 data)
  - Expected: Summary reflects input, Business Details opens
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked

- [ ] **TP01-5**: Enter business details (TD01 data)
  - Expected: All inputs appear in Summary
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked

- [ ] **TP01-6**: Enter identity & consent (TD01 data)
  - Expected: Additional Details opens
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked

- [ ] **TP01-7**: Complete additional details
  - Ownership: 90% | Same Address: Yes | Website: Yes | Profitable: Yes
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked

- [ ] **TP01-8**: Select purpose (Renovation)
  - Expected: Conditional renovation field shown, Income stage opens
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked

- [ ] **TP01-9**: Complete income & workforce (TD01 data)
  - Take-home: $80k, Outside: $15k, Expected annual: $1,140,000
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked

- [ ] **TP01-10**: Complete demographics (Decline)
  - Expected: References stage opens
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked

- [ ] **TP01-11**: Complete references (Personal only per Q13)
  - Expected: No errors, bank-link stage opens
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked

- [ ] **TP01-12**: Connect bank via Plaid
  - Sandbox ID: ________________  Account ID: ________________
  - Expected: Correct account linked
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked

- [ ] **TP01-13**: Verify second email OTP
  - Generated OTP: ________________  Date: _______  Result: ✓ / ✗ / Blocked

- [ ] **TP01-14**: Capture confirmation output
  - Generated ID: ________________  Amount: $25,000.00  Status: New Entered
  - Purpose: Renovation  Borrower: _____________  Business: _____________
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked

- [ ] **TP01-15**: Verify LOS reconciliation
  - LOS ID Found: ✓ / ✗  Stage: Intake  Status: New Entered
  - Amount Match: ✓ / ✗  Purpose Match: ✓ / ✗  No Duplicates: ✓ / ✗
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked

**Smoke Test Exit Criteria**:
- [ ] All 15 steps passed with evidence
- [ ] Generated application ID captured
- [ ] LOS record found and reconciled
- [ ] No duplicate records from retries
- [ ] Build/environment confirmed

---

### Phase 2: Functional Tests (P1-P2)

**Test Cases**: TP02-TP34
**Data Profiles**: TD01, TD02, TD03, TD04
**Estimated Duration**: 2-3 hours
**Entry Criteria**: Smoke test passed

#### Application & Identity (TP02-TP20)
- [ ] TP02: Entry validation (mandatory fields)
  - Blockers per Q01: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP03: Amount/state boundaries
  - Blockers per Q01: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP04: First email code (Observed)
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked
- [ ] TP05: Wrong/incomplete/expired codes
  - Blockers per Q02: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP06: Resend and reuse rules
  - Blockers per Q02: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP07: Second email checkpoint
  - Blockers per Q02: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP08: Applicant summary (Observed)
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked
- [ ] TP09: Community organization referral
  - Blockers per Q03: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP10: Language/phone/name variations
  - Blockers per Q01/Q03: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP11: Business details & catalogues (Observed)
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked
- [ ] TP12: Industry change dependency
  - Blockers per Q04: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP13: Address lookup
  - Blockers per Q04: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP14: Address provider failure
  - Blockers per Q04: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP15: Business date & EIN validation
  - Blockers per Q04: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP16: Birth date & SSN handling
  - Blockers per Q05: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP17: Citizenship & SBA program
  - Blockers per Q05: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP18: Consent & terms review
  - Blockers per Q06: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP19: ECDUP01 recovery
  - Blockers per Q07: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP20: Duplicate submission prevention
  - Blockers per Q06/Q19: _____________  Date: _______  Result: ✓ / ✗ / Blocked

#### Business Data & References (TP21-TP34)
- [ ] TP21: Ownership & address selection
  - Blockers per Q08: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP22: Optional fields & preferences
  - Blockers per Q08: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP23: Renovation purpose (Observed)
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked
- [ ] TP24: Multi-purpose amounts
  - Blockers per Q09: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP25: Income annualization (Observed)
  - Expected annual: $1,140,000  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP26: Income precision & validation
  - Blockers per Q10: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP27: Income source exclusivity
  - Blockers per Q10: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP28: Household consistency
  - Blockers per Q11: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP29: Employment & hours validation
  - Blockers per Q11: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP30: Decline demographics (Observed)
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked
- [ ] TP31: Demographic categories & credit
  - Blockers per Q12: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP32: Complete both references
  - Blockers per Q13: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP33: Skip blank references
  - Blockers per Q13: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP34: Partial invalid reference
  - Blockers per Q13: _____________  Date: _______  Result: ✓ / ✗ / Blocked

**Functional Phase Exit Criteria**:
- [ ] All P1 scenarios passed or Blocked with documented reason
- [ ] P2 scenarios passed or explicitly deferred
- [ ] No critical defects blocking progression
- [ ] Evidence collected for each result

---

### Phase 3: Integration & Recovery (P1)

**Test Cases**: TP35-TP40
**Data Profile**: TD05, TD06
**Estimated Duration**: 1-1.5 hours
**Entry Criteria**: Functional tests passed

- [ ] TP35: Plaid happy path (Observed)
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked
- [ ] TP36: Plaid cancel & restart
  - Blockers per Q15: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP37: Plaid timeout & invalid identity
  - Blockers per Q15/Q19: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP38: Multiple accounts & consent
  - Blockers per Q15: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP39: Manual statement alternative
  - Blockers per Q14: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP40: Statement file validation
  - Blockers per Q14: _____________  Date: _______  Result: ✓ / ✗ / Blocked

**Integration Phase Exit Criteria**:
- [ ] All bank connection paths verified
- [ ] Error recovery tested and working
- [ ] File upload constraints enforced

---

### Phase 4: Operational Checks (P1-P2)

**Test Cases**: TP41-TP48
**Data Profile**: TD01, TD07
**Estimated Duration**: 1-1.5 hours
**Entry Criteria**: Integration tests passed

- [ ] TP41: Confirmation output (Observed)
  - Generated ID: ________________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP42: LOS reconciliation (Observed)
  - LOS Record Found: ✓ / ✗  Match Verified: ✓ / ✗  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP43: Back edit & progress
  - Blockers per Q17: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP44: Refresh & resume
  - Blockers per Q17/Q18: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP45: Access isolation (P1)
  - Date: _______  Tester: _____________  Result: ✓ / ✗ / Blocked
- [ ] TP46: Data masking & redaction (P1)
  - SSN Masked: ✓ / ✗  OTP Redacted: ✓ / ✗  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP47: Service failure & performance
  - Blockers per Q19: _____________  Date: _______  Result: ✓ / ✗ / Blocked
- [ ] TP48: Browser & accessibility (P2)
  - Chrome: ✓ / ✗  Edge: ✓ / ✗  Firefox: ✓ / ✗  Keyboard: ✓ / ✗  Date: _______  Result: ✓ / ✗ / Blocked

**Operational Phase Exit Criteria**:
- [ ] All P1 scenarios passed with evidence
- [ ] Access controls verified
- [ ] Performance within SLAs (Q19 approval)
- [ ] Accessibility requirements met
- [ ] P2 scenarios completed or deferred

---

## Regression Testing

After fixes:

- [ ] Identify affected scenarios (linked requirements)
- [ ] Re-run full smoke test (TP01)
- [ ] Re-run affected functional scenarios
- [ ] Update defect tickets with retest evidence
- [ ] Confirm no new issues introduced

**Regression Round**: _______  Date: _______  Tester: _____________

---

## Closure Checklist

### Execution Report
- [ ] Total scenarios: 48
- [ ] Passed: _____ (%) 
- [ ] Failed: _____ (%)
- [ ] Blocked: _____ (%)
- [ ] Not Run: _____ (%)
- [ ] Deferred Risks: Listed below
- [ ] Build/Environment: ________________
- [ ] Test Period: From _______ To _______

### Issue Summary
- [ ] Critical defects: _____  (Blocker for release)
- [ ] High defects: _____  (Important to fix)
- [ ] Medium defects: _____  (Nice to have)
- [ ] Low defects: _____  (Polish/future)

### Deferred Q-Decisions
List any Q-items not resolved before closure:
- [ ] Q___: ______________________________________________________________
- [ ] Q___: ______________________________________________________________

### Release Decision
- [ ] All P1 tests passed or acceptable risk accepted
- [ ] No critical/high blockers remaining
- [ ] Deferred items and impact communicated
- [ ] QA Lead signature: ______________ Date: _______
- [ ] PO/Manager approval: ______________ Date: _______

**RELEASE READY: ✓ / ✗ / Conditional (conditions listed above)**

---

## Notes & Issues

```
[Use this space for test notes, blockers, environment issues, etc.]


```

---

**Report Prepared By**: __________________  **Date**: _______

**Reviewed By**: __________________  **Date**: _______
