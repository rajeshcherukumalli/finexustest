# Finexus Ascendus Business Loan Application - Test Cases

This directory contains comprehensive test case definitions for the Ascendus business loan application (https://ascendus-portal-dev.finexusinc.ai).

## Overview

- **Test Plan**: Finexus_Application_Test_Plan.txt (48 scenarios: TP01-TP48)
- **Total Test Cases**: 48 scenarios covering 18 functional requirements (FR01-FR18) and 2 non-functional requirements (NFR01-NFR02)
- **Test Data Profiles**: 7 test data fixtures (TD01-TD07)
- **Coverage**: End-to-end application flow, validation, error handling, integration, and operational checks

## Test Case Organization

### Files

| File | Coverage | Test Cases |
|------|----------|-----------|
| `TP01_smoke_test.yaml` | Full happy path with LOS reconciliation | TP01 |
| `TP02_TP20_application_identity.yaml` | Application entry, validation, identity, email, consent | TP02-TP20 |
| `TP21_TP34_business_references.yaml` | Business data, income, demographics, references | TP21-TP34 |
| `TP35_TP48_bank_operational.yaml` | Bank connection, operations, resilience, accessibility | TP35-TP48 |
| `test_data_fixtures.yaml` | Test data profiles (TD01-TD07) and environment setup | - |

### Test Case Categories

#### Smoke Test (P1)
- **TP01**: Full end-to-end smoke test with LOS reconciliation (basis: Observed)

#### Application & Identity (P1-P2)
- **TP02**: Entry validation - mandatory field requirements
- **TP03**: Amount and state boundaries (Q01)
- **TP04**: First valid email code verification (basis: Observed)
- **TP05**: Email code validation - wrong, incomplete, expired (Q02)
- **TP06**: Email code resend and reuse rules (Q02)
- **TP07**: Second email verification checkpoint (Q02)
- **TP08**: Applicant summary persistence (basis: Observed)
- **TP09**: Community organization referral branch (Q03)
- **TP10**: Language, phone, name variations (Q01, Q03)
- **TP11**: Business details and catalogues (basis: Observed)
- **TP12**: Industry change and sub-industry dependency (Q04)
- **TP13**: Business and home address lookup (Q04)
- **TP14**: Address provider failure handling (Q04)
- **TP15**: Business date and EIN validation (Q04)
- **TP16**: Birth date and SSN handling (Q05)
- **TP17**: Citizenship and program dependency (Q05)
- **TP18**: Terms review and consent gate (Q06)
- **TP19**: ECDUP01 recovery - duplicate identity (Q07)
- **TP20**: Repeated submission - duplicate prevention (Q06, Q19)

#### Business Data & References (P1-P2)
- **TP21**: Ownership percentage and address selection (Q08)
- **TP22**: Optional business contact and preferences (Q08)
- **TP23**: Renovation purpose selection (basis: Observed)
- **TP24**: Multiple purposes and amount totals (Q09)
- **TP25**: Annual household income calculation (Q10)
- **TP26**: Income and expense precision validation (Q10)
- **TP27**: Income source exclusivity (Q10)
- **TP28**: Household consistency validation (Q11)
- **TP29**: Employment and weekly hours validation (Q11)
- **TP30**: Decline demographics (basis: Observed)
- **TP31**: Demographic selection and credit mapping (Q12)
- **TP32**: Complete both references (Q13)
- **TP33**: Skip blank references (Q13)
- **TP34**: Partial invalid reference validation (Q13)

#### Bank & Operational (P1-P2)
- **TP35**: Plaid happy path (basis: Observed)
- **TP36**: Plaid cancel and restart (Q15)
- **TP37**: Plaid timeout and invalid identity (Q15, Q19)
- **TP38**: Multiple accounts and consent verification (Q15)
- **TP39**: Manual bank statement alternative (Q14)
- **TP40**: Statement file validation (Q14)
- **TP41**: Confirmation output capture (basis: Observed)
- **TP42**: LOS record reconciliation (basis: Observed)
- **TP43**: Back edit and progress tracking (Q17)
- **TP44**: Form refresh and resume functionality (Q17, Q18)
- **TP45**: Applicant and LOS access isolation (Q18)
- **TP46**: Data masking and evidence redaction (Q18)
- **TP47**: Service failure and performance testing (Q19)
- **TP48**: Browser and keyboard accessibility (Q01, Q17)

## Test Data Profiles (TD01-TD07)

| Profile | Purpose | Use Cases |
|---------|---------|-----------|
| **TD01** | Successful Renovation application (base) | TP01, TP04, TP08, TP11, TP16, TP18, TP23, TP25, TP30, TP35, TP41, TP42, TP48 |
| **TD02** | Field validation and boundaries | TP02, TP03, TP10, TP12, TP15, TP16, TP26, TP29 |
| **TD03** | Email verification failures | TP05, TP06 |
| **TD04** | Conditional and optional branches | TP09, TP21, TP22, TP24, TP27, TP31, TP32, TP33, TP43 |
| **TD05** | Bank connection and file paths | TP35, TP36, TP37, TP38, TP39, TP40 |
| **TD06** | Recovery and persistence | TP14, TP19, TP20, TP44, TP47 |
| **TD07** | Privacy and access isolation | TP45, TP46 |

## Key Testing Attributes

### Requirement Coverage
- **Functional Requirements**: FR01-FR18 (18 requirements)
- **Non-Functional Requirements**: NFR01 (access/privacy), NFR02 (reliability/performance)

### Approval Checkpoints (Q01-Q19)
Test cases are marked with dependency on specific business rule confirmations (Q01-Q19). These must be resolved before scenarios can transition from Proposed/Inferred to Observed.

### Priority Levels
- **P1** (Critical): Core functionality, happy path, identity/consent, access isolation
- **P2** (Important): Edge cases, boundary conditions, optional fields, usability

### Test Basis
- **Observed**: Verified in demonstration video
- **Proposed**: Based on requirements, awaiting Q-decision approval
- **Inferred**: Derived from requirements

## Environment Setup

### Required Variables (from .env)
```bash
QA_EMAIL=your-test-mailbox@example.com
QA_LOGIN_URL=https://ascendus-portal-dev.finexusinc.ai/login
PLAID_SANDBOX_ID=user_good
PLAID_SANDBOX_CODE=code_sandbox_success
PLAID_ACCOUNT_ID=15614c876fa1f9ae58dd7a5d3efb30
LOS_ADMIN_USERNAME=admin@finexus.ai
LOS_ADMIN_PASSWORD=***
```

### Optional Variables
```bash
QA_NAVIGATION_TIMEOUT_MS=90000
QA_BUTTON_PROBE_LIMIT=30
```

## Execution Phases

1. **Preparation**: Resolve Q-decisions, provision data, configure environments
2. **Smoke** (TP01): Full happy path with LOS reconciliation
3. **Functional** (TP02-TP34): Validation, business data, references
4. **Integration & Recovery** (TP35-TP40): Bank, statements, error recovery
5. **Operational** (TP41-TP48): Confirmation, access, performance, accessibility
6. **Regression**: Re-run affected paths after fixes
7. **Closure**: Review failures, confirm release readiness

## Execution Status

Track per test case:
- **Pass**: Requirement met, evidence attached
- **Fail**: Requirement not met, defect raised
- **Blocked**: Q-decision not approved or dependency unmet
- **Not Run**: Deferred per product decision

## Evidence Requirements

For each test case result, capture:
- Scenario ID, Requirement ID, Data Profile, Test Date
- Build/Environment (version and URL)
- Tester name and execution date
- Actual output and generated application ID (if applicable)
- Status and evidence link
- For failures: reproducible steps, expected vs. actual, severity

## Defect Recording

Defects should include:
- Reproducible steps and environment
- Expected vs. actual behavior
- UI/request/response evidence (redacted)
- Record state and application ID
- Linked requirement ID(s)
- Severity classification

## Q-Decision References

Unresolved business rule Q-decisions block associated test scenarios:

| Q# | Topic | Scenarios |
|----|-------|-----------|
| Q01 | Field validation limits | TP02, TP03, TP10, TP48 |
| Q02 | Email OTP expiry/resend | TP05, TP06, TP07 |
| Q03 | Referral dependencies | TP09, TP10 |
| Q04 | Address/business validation | TP12, TP13, TP14, TP15 |
| Q05 | Identity/citizenship rules | TP16, TP17 |
| Q06 | Consent/submission idempotency | TP18, TP20 |
| Q07 | ECDUP01 error handling | TP19 |
| Q08 | Ownership/address logic | TP21, TP22 |
| Q09 | Multi-purpose calculation | TP24 |
| Q10 | Income annualization | TP25, TP26, TP27 |
| Q11 | Household/employment | TP28, TP29 |
| Q12 | Demographics/credit impact | TP31 |
| Q13 | Reference requirements | TP32, TP33, TP34 |
| Q14 | Manual statement option | TP39, TP40 |
| Q15 | Plaid integration | TP36, TP37, TP38 |
| Q17 | Back-navigation/tracking | TP43, TP48 |
| Q18 | Auth/access isolation | TP44, TP45, TP46 |
| Q19 | Performance/duplicates | TP20, TP37, TP47, TP48 |

## Notes

- All test cases reference the Finexus Application Test Plan v1.0 (2026-10-07)
- Never use production data; all fixtures are synthetic and approved for QA only
- Maintain fresh email addresses for each execution (per TD01 provisioning)
- Keep Plaid sandbox configuration current with approved test institution
- Use approved LOS ADMIN account for reconciliation only
- Redact SSN, OTP, and bank credentials in all evidence
- Document any deferred Q-decisions as risks before test execution

## Related Documentation

- **Test Plan**: Finexus_Application_Test_Plan.txt
- **Application Contract**: ../../../data/contracts/ascendus-contract.json
- **Guide**: ../../../GUIDE.md
- **Process**: ../../../PROCESS.md
- **Requirements**: Finexus_Application_Requirements.docx v1.0
- **Recording**: application_creation_flow.mp4
