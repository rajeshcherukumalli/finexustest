# Finexus LOS - Simple Test Plan & Test Cases

## Overview

This directory contains comprehensive test cases for the **Finexus Loan Origination System (LOS)** admin portal, focusing on the core workflow demonstrated in the recording.

- **Plan Version**: 1.0
- **Status**: Draft for Review
- **Test Cases**: 7 core checks (TC01-TC07)
- **Focus**: LOS access, application management, qualification, acceptance, borrower review, stage transitions, and validation

## Directory Structure

```
tests/testcases/los/
├── TC01_TC07_los_core_workflow.yaml    # Complete test case definitions
├── README.md                           # This file
└── [Additional files as needed]
```

## Test Cases Overview

| Test Case | Requirement | Priority | Description |
|-----------|-------------|----------|-------------|
| **TC01** | R01 | P1 | Access LOS from LMS and view Loan Applications |
| **TC02** | R02 | P1 | Open application dashboard with correct details |
| **TC03** | R03 | P1 | Run qualification and display Eligibility status |
| **TC04** | R04 | P1 | Accept application and enable Proceed to Lending |
| **TC05** | R05 | P1 | Review borrower info in Parties & Credit tab |
| **TC06** | R06 | P1 | Move application from Intake to Lending stage |
| **TC07** | R07 | P1 | Block Underwriting without program selection |

## Requirements Coverage

### Functional Requirements (R01-R07)

- **R01**: LOS Access - User can switch from LMS to LOS
- **R02**: Application Details - Dashboard displays correct ID, status, stage, business info
- **R03**: Qualification - Eligible app shows Eligibility with Accept action
- **R04**: Acceptance - Accept shows success result, enables Proceed to Lending
- **R05**: Borrower Review - Parties & Credit displays borrower and credit info
- **R06**: Lending Transition - Proceed to Lending moves stage Intake → Lending
- **R07**: Program Validation - Block Underwriting without program selection

## Test Execution Flow

```
TC01: Access LOS
  ↓
TC02: Open Application
  ↓
TC03: Run Qualification
  ↓
TC04: Accept Application
  ↓
TC05: Review Borrower Info
  ↓
TC06: Move to Lending
  ↓
TC07: Validate Program Selection
```

**Execution Model**: Sequential on same test application
- All tests execute on the same prepared application
- Previous test results inform subsequent tests
- Application progresses through workflow stages TC01-TC07

## Test Data Requirements

### Prerequisites
- Approved QA environment (LMS and LOS URLs)
- Authorised ADMIN account with full access
- Existing New Entered application at Intake that is eligible
- Application and borrower data available for verification
- Qualification service configured
- No program selected for TC07 validation test

### Test Data Profile: LOS_QA01

```yaml
Environment: https://los.finexusinc.ai (QA)
Credentials: QA_LOS_ADMIN_USERNAME / QA_LOS_ADMIN_PASSWORD
Application:
  ID: {{QA_APPLICATION_ID}}
  Status: New Entered
  Stage: Intake
  Business: {{QA_BUSINESS_NAME}} ({{QA_BUSINESS_TYPE}})
  Start Date: {{QA_BUSINESS_START_DATE}}
Borrower:
  Name: {{QA_BORROWER_NAME}}
  Ownership: {{QA_OWNERSHIP_PERCENT}}%
  DOB: {{QA_BORROWER_DOB}}
  Address: {{QA_BORROWER_ADDRESS}}
Qualification:
  Eligible: true
  Reason: Meets all qualification criteria
```

## Evidence & Documentation

### Required for Each Test
- Application ID (record for all cases)
- Status display screenshots (at each status change)
- Stage transition screenshots (before/after each transition)
- TC07 validation message screenshot (exact text required)
- Build/version information
- Date and tester name

### Critical Screenshots
1. **TC01**: Loan Applications list loaded
2. **TC02**: Dashboard with correct status/stage/business info
3. **TC03**: Eligibility status displayed with Accept button
4. **TC04**: Success notification and Proceed to Lending button
5. **TC05**: Parties & Credit tab with borrower details
6. **TC06**: Stage transitions (Intake → Lending)
7. **TC07**: Validation error message and Program & Pricing tab

## Key Test Assertions

### TC01: LOS Access
- ✅ LOS page loads
- ✅ Loan Applications list is visible
- ✅ User is authenticated

### TC02: Application Dashboard
- ✅ Correct application ID displayed
- ✅ Status is "New Entered"
- ✅ Stage is "Intake"
- ✅ Business information matches QA source

### TC03: Run Qualification
- ✅ Qualification completes
- ✅ Status shows "Eligibility"
- ✅ Accept action available
- ✅ Application ID retained

### TC04: Accept Application
- ✅ Success notification appears
- ✅ Proceed to Lending becomes available
- ✅ Stage remains "Intake"
- ✅ Status remains "Eligibility"

### TC05: Parties & Credit
- ✅ Tab loads and shows borrower
- ✅ Borrower name matches QA data
- ✅ Ownership percentage displayed
- ✅ Personal information visible
- ✅ Credit information visible
- ✅ Stage unchanged

### TC06: Move to Lending
- ✅ Transition successful
- ✅ Intake marked as complete
- ✅ Lending stage active
- ✅ Application ID retained
- ✅ Status remains "Eligibility"
- ✅ Move to Intake and Proceed to Underwriting available

### TC07: Program Validation
- ✅ Underwriting blocked without program selection
- ✅ Exact validation message displayed
- ✅ Program & Pricing tab opens
- ✅ Application remains at Lending stage
- ✅ Does not enter Underwriting

## Test Status & Results

| Test Case | Status | Notes |
|-----------|--------|-------|
| TC01 | ⏳ Pending | Awaiting execution |
| TC02 | ⏳ Pending | Awaiting execution |
| TC03 | ⏳ Pending | Awaiting execution |
| TC04 | ⏳ Pending | Awaiting execution |
| TC05 | ⏳ Pending | Awaiting execution |
| TC06 | ⏳ Pending | Awaiting execution |
| TC07 | ⏳ Pending | Awaiting execution |

## Environment Configuration

### LOS QA Environment
```
LMS URL: https://lms-dev.finexusinc.ai
LOS URL: https://los.finexusinc.ai
Admin Account: {{QA_LOS_ADMIN_USERNAME}}
```

### Timeouts & Performance
- Qualification processing: {{QUALIFICATION_TIMEOUT_MS}} ms
- Application acceptance: {{ACCEPTANCE_TIMEOUT_MS}} ms
- Stage transition: {{STAGE_TRANSITION_TIMEOUT_MS}} ms
- No strict SLA defined; log delays for investigation

## Items Requiring Confirmation

- [ ] Exact qualification rules and approved eligible test data
- [ ] Confirm Eligibility status after acceptance/Lending transition is intended
- [ ] Verify environment pairing (lms-dev ↔ los-dev)
- [ ] Program selection and Underwriting progression (separate recording needed)

## Out of Scope

❌ Application creation workflow  
❌ Full field validation across tabs  
❌ Other user roles (Underwriter, Compliance, etc.)  
❌ System integrations (credit bureaus, email, etc.)  
❌ Withdraw/Decline workflows  
❌ Later loan stages (Underwriting, Closing, Funding)

## Acceptance Criteria

✅ All 7 test cases pass with correct data and behaviors  
✅ All stage transitions verified  
✅ Validation blocking works as designed  
✅ Evidence captured and documented  
✅ Ready for extended testing (full workflows, other roles, integrations)

## Next Steps

1. **Confirm prerequisites** - All prerequisites met and ready
2. **Prepare test data** - QA application at Intake, eligible for qualification
3. **Execute tests TC01-TC07** - Sequential execution on same application
4. **Capture evidence** - Screenshots and logs from each test
5. **Document results** - Record Pass/Fail/Blocked for each case
6. **Review findings** - Project owner acceptance of results
7. **Plan extended testing** - Scope for additional workflows and roles

## References

- **Test Plan**: Finexus_LOS_Simple_Test_Plan.txt
- **Recording**: LOS workflow demo (application progression through Intake → Lending)
- **Requirements Document**: Finexus_Application_Requirements.docx
- **Related Test Plan**: Ascendus Portal Application (separate module)

---

**Last Updated**: 2026-10-08  
**Version**: 1.0  
**Status**: Ready for Execution
