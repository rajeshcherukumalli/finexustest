# LOS Portal Testing - Execution Roadmap

**Status**: ✅ Step 1 Complete - Portal Scraped  
**Date**: 2026-10-08  
**Overall Progress**: 20% (1 of 5 steps complete)

---

## Completed ✅

### Step 1: Scrape LOS Portal
- ✅ Scraped: https://los.finexusinc.ai
- ✅ Detected: Authentication required (protected)
- ✅ Contract created: `data/contracts/los-contract.json` (1.2 KB)
- ✅ Workspace config: `data/output/los/workspace.json`

**Findings**:
- Portal requires admin login (expected)
- Single protected page detected (login page)
- Navigation elements not accessible without authentication
- Contract successfully created for protected portal

---

## Remaining Steps

### Step 2: Generate Playwright Specs ⏳ (Next)
**What**: Convert YAML test cases to Playwright automation scripts  
**Output**: Automated test files for TC01-TC07  
**Status**: Ready to execute  

**Action**:
```bash
# From finexustest directory
/playwright-gen los TC01_TC07  # Will generate specs from YAML
```

**Deliverables**:
- `tests/specs/los/TC01_TC07_los_workflow.spec.ts`
- `tests/specs/pages/LosPage.page.ts` (Page Object Model)

---

### Step 3: Set Up Environment ⏳
**What**: Configure credentials and test data  
**Required**:
- [ ] LOS admin credentials (.env.qa)
- [ ] Test application ID (at Intake stage, eligible)
- [ ] Business/borrower data for verification
- [ ] Qualification service confirmation

**Files to Update**:
1. `data/output/los/.env.qa` (Create from template)
2. Test data values in `TC01_TC07_los_core_workflow.yaml`

**Action**:
```bash
# Create .env.qa for LOS
cp data/output/ascendus/.env.qa.example data/output/los/.env.qa

# Fill in:
# QA_LOS_BASE_URL=https://los.finexusinc.ai
# QA_LOS_USERNAME=<admin-username>
# QA_LOS_PASSWORD=<admin-password>
# QA_APPLICATION_ID=<existing-app-id>
```

---

### Step 4: Run Tests TC01-TC07 ⏳
**What**: Execute the 7 core LOS workflow tests  
**Execution**: Sequential (must run in order)  
**Environment**: Headed mode (visible browser)  

**Action**:
```bash
npx playwright test tests/specs/los/ --headed
```

**Tests to Run** (in order):
1. TC01: Access LOS ✓
2. TC02: Open Application Dashboard ✓
3. TC03: Run Qualification ✓
4. TC04: Accept Application ✓
5. TC05: Review Parties & Credit ✓
6. TC06: Move to Lending ✓
7. TC07: Block Underwriting ✓

**Expected Duration**: ~10-15 minutes per full execution

---

### Step 5: Document Results ⏳
**What**: Capture and analyze test results  

**Required Evidence**:
- Screenshots of each test stage
- Status displays and transitions
- Validation messages (especially TC07)
- Test execution log
- Build/environment version

**Output**:
- Test execution report
- Evidence artifacts
- Pass/Fail summary per test case
- Findings and recommendations

---

## Complete Execution Timeline

```
Step 1: Scrape Portal          ✅ DONE    (5 min)
Step 2: Generate Specs         ⏳ READY   (10 min) 
Step 3: Configure Environment  ⏳ READY   (5 min)
Step 4: Run Tests TC01-TC07    ⏳ READY   (15 min)
Step 5: Document Results       ⏳ READY   (10 min)
                                          --------
Total Estimated Time:                     ~45 min
```

---

## Files Generated So Far

✅ **Contracts**
- `data/contracts/los-contract.json` (1.2 KB) - LOS portal structure

✅ **Configuration**
- `data/output/los/workspace.json` - LOS test environment config

✅ **Test Cases**
- `tests/testcases/los/TC01_TC07_los_core_workflow.yaml` (572 lines)
- `tests/testcases/los/README.md` (238 lines)

⏳ **Automation Scripts** (To be generated)
- `tests/specs/los/TC01_TC07_los_workflow.spec.ts` (Pending Step 2)
- `tests/specs/pages/LosPage.page.ts` (Pending Step 2)

---

## Key Information for Execution

### LOS Portal Details
- **URL**: https://los.finexusinc.ai
- **Auth Type**: Admin login required
- **Test Order**: Strict sequential (TC01 → TC07)
- **Single Application**: All tests use same app, progressing through stages

### Test Application Requirements
- **Status**: New Entered
- **Stage**: Intake
- **Qualification**: Eligible (must pass qualification rules)
- **Program**: None (for TC07 validation)

### Success Criteria
- ✅ All 7 tests pass
- ✅ Application progresses: Intake → Lending
- ✅ Stage transitions captured
- ✅ Validation message (TC07) exact match
- ✅ No unintended state changes

---

## Next Action

Ready to proceed with **Step 2: Generate Playwright Specs**

Options:
1. **Auto-generate** - Create specs automatically from YAML
2. **Manual review** - Review YAML first, then generate
3. **Skip to Step 3** - Set up environment first, generate specs later

**Recommendation**: Start with Step 3 (Environment Setup) to gather credentials, then return to Step 2 (Generate Specs), then Step 4 (Run Tests).

---

## Risk & Assumptions

### Assumptions
- ✓ LOS admin account available with full workflow access
- ✓ Test application exists at Intake, eligible for qualification
- ✓ Qualification service configured and responding
- ? Program selection field exists in Program & Pricing tab

### Risks
- **Credentials Missing**: Cannot proceed without admin login
- **Test Application**: If app doesn't exist or is progressed, may block tests
- **Service Dependencies**: Qualification, stage transition services must be available

### Mitigation
- Confirm all prerequisites before Step 4
- Have backup test application ready
- Verify services are available and responding
- Test login separately (before Step 4)

---

## Getting Help

If tests fail:
1. Check **BLOCKERS** section in each test case YAML
2. Verify **PREREQUISITES** in README.md
3. Review **ENVIRONMENT** configuration
4. Check LOS service status and logs
5. Verify test data matches QA source records

---

**Progress**: 20% Complete (1/5 steps)  
**Next Milestone**: Environment configured and credentials ready  
**Ready to Continue**: Yes ✓

