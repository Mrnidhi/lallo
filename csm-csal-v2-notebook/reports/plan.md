# Sales AI V3 Plan

This is the current agreed V3 scope. It supersedes the arm definitions in the earlier full-Gold normalization proposal.

## Three comparison arms

| Arm | Source and approach | Agent test |
|---|---|---|
| A | Existing production tables and existing production implementation | Ask the production agent the test questions and record its responses |
| B | All six Sales AI Gold tables, organized into personal facts and dimensions with clear business grains | Give business views to Genie agents and test them |
| C | Normalize `csm_csal_summary` through code into actual personal tables with validated keys and relationships | Give the normalized tables directly to Genie agents and test them |

Arm B covers `csm_csal_summary`, `fincon_issues`, `sales_ai_roster`, `sales_ai_case_ledger`, `sales_ai_case_issues` and `tea_deliverables` under `dev.sales_ai_assistant_gold`.

Separate measures by what each row represents. Preserve every source column and validate relationships before relying on them. Normalization cannot recover identifiers or history already removed from the source.

## Reuse the existing V2 work

Start by reviewing the existing V2 assets. Reuse code, documentation, question definitions, validation checks and agent settings wherever they fit the V3 scope.

Check source versions, schemas, grain, column coverage and business logic before reusing V2 tables or views. Reuse a question only after checking its expected answer against the chosen V3 data. Reuse agent settings as a starting point, then verify their source bindings and supported capabilities.

Keep V2 intact. V3-specific edits belong in the V3 directory or V3 personal objects. Reference reusable V2 assets instead of making unnecessary copies. An asset needing changes gets a V3 version so earlier V2 results remain reproducible.

## Proposed Databricks workspace organization

This tree describes the agreed organization. It does not mean the folders or notebooks already exist. Notebook entries are proposed responsibilities; reuse existing V2 work before creating each entry.

```text
Your personal workspace/
|
+-- Existing V2 work/
|
+-- Sales_AI_V3/
    |
    +-- 00_Project/
    |   +-- Plan
    |   +-- Progress
    |
    +-- 01_Data_Review/
    |   +-- 01_Source_Inventory
    |   +-- 02_Column_and_Grain_Review
    |
    +-- 02_Arm_A_Production_Test/
    |   +-- 01_Production_Agent_Test
    |
    +-- 03_Arm_B_Facts_Dimensions_Views/
    |   +-- 01_Build_Dimensions
    |   +-- 02_Build_Facts
    |   +-- 03_Build_Agent_Views
    |   +-- 04_Validate_Model
    |
    +-- 04_Arm_C_Normalized_CSAL/
    |   +-- 01_Build_Normalized_Tables
    |   +-- 02_Validate_Model
    |
    +-- 05_Genie_Configuration/
    |   +-- Arm_B_Instructions_and_Examples
    |   +-- Arm_C_Instructions_and_Examples
    |   +-- Agent_and_UC_Function_Register
    |
    +-- 06_Benchmark/
        +-- 01_Question_Bank_and_Expected_Answers
        +-- 02_Run_Comparison
        +-- 03_Results_and_Charts
```

Workspace folders contain notebooks and documents. Tables and views live in the approved personal catalog schema; Genie agents are separate assets. Record their names and links in the project documentation. Names such as `v3_b_dim_customer` and `v3_c_customer` illustrate the proposed naming convention, not deployed objects.

## Agent preparation and comparison

- Review production's existing instructions, examples and UC functions.
- Give the personal agents equivalent business guidance adapted to their own sources, with verified joins and calculations.
- Use preparation questions for tuning, then freeze configurations before scored tests.
- Validate column and record preservation, measure reconciliation, key uniqueness and join duplication first.
- Compare CSM/CSAL questions across A, B and C. Compare other Gold domains across A and B because C covers only CSM/CSAL.
- Use the same applicable questions, date filters and verified expected answers. Record source timestamps and configuration differences.
- Repeat each scored question three times. Retain answers, SQL when available, errors and timing.
- Report accuracy, consistency, SQL complexity and response time. Explain data or configuration differences affecting the comparison.

## Next step

Review the V2 asset inventory and identify what can be reused, what needs a V3 revision and what is missing. Confirm actual source schemas, keys and the reporting period from evidence before building the personal models.
