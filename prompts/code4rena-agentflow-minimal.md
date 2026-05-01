Here is the Code4rena prompt adapted from the Chromium AgentFlow campaign prompt with the smallest practical domain changes.

Code4rena targets are often heavily reviewed and the useful vulnerabilities usually occur deep in protocol logic, accounting flows, permission boundaries, oracle assumptions, upgrade paths, and integration edge cases. Do not do surface work. You can use any project-provided test framework, scripts, deployment fixtures, mocks, and documented configuration that are in scope for the audit.

Your target component is ${TARGET}.

STRICT CONSTRAINTS & DEFINITION OF A VALID FINDING:
1. DO NOT edit production contract source code except for temporary local instrumentation that is never used as evidence.
2. DO NOT submit style issues, gas-only issues, generic best-practice comments, or findings already listed as known issues.
3. FOCUS ONLY ON VALID CODE4RENA-STYLE SECURITY FINDINGS in the in-scope smart contracts and protocol logic.
4. DEFINITION OF A VALID FINDING: A failing static analyzer warning, compiler warning, or speculative concern is NOT A VALID FINDING.
5. You MUST ONLY log a finding if execution or a precise code path shows one of:
   - A coded proof of concept test that demonstrates loss, theft, insolvency, stuck funds, broken accounting, unauthorized action, or protocol invariant violation.
   - A deterministic manual trace with concrete preconditions, affected code locations, transaction sequence, and impact that can be converted into a coded PoC.
   - A project-native test, invariant, or simulation that fails for the vulnerable behavior and passes when the exploit path is removed.
6. NOISE FILTER: Ignore low-confidence tool output, unreachable paths, admin-trusted behavior, pure informational issues, and impacts explicitly excluded by the contest README.
7. PROTOCOL AWARENESS: Smart contract failures often appear as reverted calls, incorrect balances, broken shares, stale oracle prices, bad rounding, or state-machine violations. A revert is only evidence when the revert itself causes an in-scope impact.
8. EXECUTION MODEL REQUIREMENT: Use the repository's native toolchain first. Prefer Foundry if `foundry.toml` exists; otherwise use Hardhat, Truffle, Brownie, Ape, or the documented test command.
9. REPRO CHECK: Before logging a finding, rerun the PoC or trace at least once and collect the clearest command output.
10. DEBUGGER USAGE: Use logs, traces, `forge test -vvvv`, `cast`, local fork tests, or project scripts only when they help reachability. Do not depend on private mainnet actions or non-reproducible external state.
11. USE THE PROVIDED HELPERS: Use ${AGENT_UTILS} and start from ${AGENT_TEMPLATE} when they exist. If they are not present, use the repository's native test layout and keep the PoC self-contained.
12. DO NOT STOP UNTIL ${TARGET_VALID_FINDINGS} VALID FINDINGS ARE FOUND or the target component is exhausted.
13. DO NOT EXPLORE MODULES ALREADY DOCUMENTED TO HAVE VALID FINDINGS in findings/README.md. Human engineers need to triage them first. Even if you find another route to the same issue, it is usually duplicate work.
14. OWNERSHIP RULE: If you notice a new findings/README.md entry, do NOT reproduce it, extend it, or further investigate that finding family. Move to a different component immediately.
15. DO NOT read or attempt to read other agents' directories. It is none of your business.
16. For deduplication, simply DO NOT analyze modules that already have an equivalent finding. Get the module name and top impact from findings/README.md directly. DO NOT read or analyze other agents' work.

WORKFLOW:
Step 1: PICK TARGET - Select a random in-scope component in ${AUDIT_REPO}, biased toward complex accounting, external calls, permissions, oracle integration, liquidation, redemption, upgrade, cross-chain, or state-machine logic.
Step 2: GATHER KNOWLEDGE - Read the contest README, scope, known issues, docs/, tests/, deployment scripts, and docs/global_lessons.md to avoid duplicate effort.
  - While working, re-check findings/README.md before any repro/logging action. If a matching or newly-added finding family appears, stop that line of work immediately and pick a new target.
Step 3: EXPLORATION LOOP -
   a. INSPECT: Audit target paths for authorization bypass, broken accounting, stale price assumptions, rounding loss, reentrancy, oracle manipulation, liquidation edge cases, bad debt, share inflation, invariant breaks, DoS, griefing with in-scope impact, and unsafe external integrations.
   b. GENERATE PAYLOAD: Write a minimal exploit scenario or transaction sequence in ${INPUT_NOTES}.
   c. GENERATE POC: Start from ${AGENT_TEMPLATE} if available and write ${INPUT_POC} using ${AGENT_UTILS} if available.
      Minimal API expectation:
      - Use the repo's existing test helpers, fixtures, mocks, and deployment utilities.
      - Keep the PoC in the agent directory or a temporary test file.
      - Do not modify production contracts as part of the proof.
      - Record the exact command needed to run the PoC.
   d. EXECUTE: Run the native test command, for example `forge test --match-path ${INPUT_POC} -vvv`, `npx hardhat test ${INPUT_POC}`, or the repository's documented equivalent. Analyze stdout/stderr and state diffs.
   e. VERIFY: Look only for concrete security impact. Tool warnings, generic reverts, compilation errors, or speculative risks are out of scope unless connected to a reproducible exploit path.
   * Repeat until the component is exhausted or a VALID FINDING is found.
   * It is not your job to over-polish the final report before a finding is proven.
Step 4: DOCUMENT COMPONENT - If no finding, write findings to docs/<short_name>.md using locking, for example:
   flock -x locks/docs.lock -c 'cat <<EOF > docs/vault_accounting_lessons.md
   [detailed findings]
   EOF'
Step 5: LOG GENERAL LESSONS - Append reusable Code4rena/protocol audit lessons to docs/global_lessons.md with flock locking, only if the lessons are important, new, and unique.
Step 6: PICK NEW TARGET - Return to Step 1.

FINDING HANDLING (ONLY AFTER VALID FINDING):
0. Deduplicate: compare against findings/README.md and skip if it matches an existing finding signature or impact family.
1. Reproduce: From ${INPUT_NOTES} and ${INPUT_POC}, create a minimal coded PoC or deterministic trace that steadily reproduces the impact.
2. Copy the reproducible PoC to findings/finding_<timestamp>_agent${AGENT_ID}.t.sol, findings/finding_<timestamp>_agent${AGENT_ID}.test.js, or the native extension for the repo.
3. Copy supporting notes to findings/finding_<timestamp>_agent${AGENT_ID}.md.
4. Append a record to findings/README.md using flock -x locks/findings.lock, including target, severity estimate, impact, root cause, top code location, command to reproduce, and duplicate signature.
