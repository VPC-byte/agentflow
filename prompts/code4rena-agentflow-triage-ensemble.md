Here is the Code4rena ensemble prompt adapted from the Chromium AgentFlow campaign prompt while preserving the original multi-agent campaign structure.

Code4rena targets are heavily reviewed and useful vulnerabilities usually occur deep in protocol-specific flows. Do not do surface work. Each shard must own a narrow target, produce reproducible evidence, and avoid duplicating other shards. The campaign succeeds through coverage of different economic paths, not through many agents repeating the same obvious checks.

Your target component is ${TARGET}.

STRICT CONSTRAINTS & DEFINITION OF A VALID FINDING:
1. DO NOT edit production contract source code except temporary local instrumentation that is removed before evidence is logged.
2. DO NOT log style, gas-only, documentation, generic linter, unsupported centralization, or known-issue reports.
3. FOCUS ONLY ON CODE4RENA-STYLE SECURITY FINDINGS in in-scope contracts, tests, scripts, and integrations.
4. DEFINITION OF A VALID FINDING: An agent opinion, tool warning, or suspicious code smell is NOT A VALID FINDING.
5. You MUST ONLY log a finding if execution or a precise trace shows one of:
   - A coded PoC demonstrating direct or indirect loss, theft, stuck funds, insolvency, unauthorized action, broken accounting, oracle manipulation, or invariant violation.
   - A deterministic transaction sequence with concrete preconditions, affected code locations, expected vs actual state, and impact.
   - A failing invariant, fuzz, fork, or project-native test that proves in-scope protocol behavior is unsafe.
6. NOISE FILTER: Ignore duplicate impact, excluded risks, test-only behavior, admin-trusted behavior, impossible preconditions, pure tool output, and low-value observations without measurable impact.
7. PROTOCOL AWARENESS: The strongest findings often cross contract boundaries. Track assets, shares, debt, collateral, oracle prices, rewards, permissions, callback order, upgrade state, and external integration assumptions across the full call path.
8. PROCESS MODEL REQUIREMENT: Use the repo's native framework. Prefer Foundry; otherwise use Hardhat, Truffle, Brownie, Ape, or the documented command. Do not create a parallel test framework unless necessary.
9. REPRO CHECK: Before logging a finding, rerun the PoC or trace at least once and collect the clearest command output.
10. TRIAGE USAGE: Use traces, balance snapshots, invariant assertions, fork simulations, and static tools to support a hypothesis. Do not submit static tool output as the finding.
11. USE THE PROVIDED HELPERS: Use ${AGENT_UTILS} and start from ${AGENT_TEMPLATE} when they exist. If unavailable, clone the nearest existing project test pattern.
12. DO NOT STOP UNTIL ${TARGET_VALID_FINDINGS} VALID FINDINGS ARE FOUND or your assigned shard scope is exhausted.
13. DO NOT EXPLORE MODULES ALREADY DOCUMENTED TO HAVE VALID FINDINGS in findings/README.md. Human engineers need to triage them first. Another route to the same impact is usually duplicate work.
14. OWNERSHIP RULE: If you notice a new findings/README.md entry, do NOT reproduce it, extend it, or further investigate that finding family. Move to a different component immediately.
15. DO NOT read or attempt to read other agents' directories. It is none of your business.
16. For deduplication, simply DO NOT analyze modules that already have an equivalent finding. Use findings/README.md for module, impact, and signature only. DO NOT read or analyze other agents' work.

WORKFLOW:
Step 1: PICK TARGET - Select a random in-scope component in ${AUDIT_REPO} within your shard assignment ${SHARD_FOCUS}. Bias toward paths other shards are less likely to cover: cross-contract accounting, rewards, integrations, liquidation edge cases, oracle assumptions, upgrade/initializer paths, bridge/message handlers, queue/state-machine transitions, and uncommon withdrawal/redemption paths.
Step 2: GATHER KNOWLEDGE - Read the contest README, scope, known issues, architecture docs, existing tests, deployment scripts, docs/global_lessons.md, and findings/README.md.
  - While working, re-check findings/README.md before any repro/logging action. If a matching or newly-added finding family appears, stop that line of work immediately and pick a new target.
Step 3: EXPLORATION LOOP -
   a. INSPECT: Audit the assigned path and write a local hypothesis: attacker, victim, preconditions, transaction sequence, vulnerable check/state update, violated invariant, impact, and likely severity.
   b. GENERATE PAYLOAD: Write the hypothesis and exploit sequence to ${INPUT_NOTES}. Include the dedup signature: target contract, function path, root cause, and impact class.
   c. GENERATE POC: Start from ${AGENT_TEMPLATE} if available and write ${INPUT_POC} using ${AGENT_UTILS} if available.
      Minimal API to use:
      - Reuse existing fixtures and deployment helpers.
      - Keep the PoC minimal and isolated to your shard.
      - Include explicit assertions for balances, shares, debt, ownership, permissions, oracle price, queue state, or invariant deltas.
      - Record the exact command and expected evidence lines.
      - Keep all scratch files inside ${AGENT_DIR}.
   d. EXECUTE: Run the native test command, such as `forge test --match-path ${INPUT_POC} -vvvv` or `npx hardhat test ${INPUT_POC}`, and analyze stdout/stderr.
   e. VERIFY: Confirm impact, scope, non-duplication, and reproducibility. If the finding is weak, document the lesson and continue instead of logging it.
   * Repeat until the shard is exhausted or a VALID FINDING is found.
   * It is not your job to analyze every related module after a valid duplicate signature exists.
Step 4: DOCUMENT COMPONENT - If no finding, write findings to docs/<short_name>.md using locking, for example:
   flock -x locks/docs.lock -c 'cat <<EOF > docs/liquidation_edge_lessons.md
   [detailed findings]
   EOF'
Step 5: LOG GENERAL LESSONS - Append reusable Code4rena audit lessons to docs/global_lessons.md with flock locking, only if the lessons are important, new, and unique.
Step 6: PICK NEW TARGET - Return to Step 1.

FINDING HANDLING (ONLY AFTER VALID FINDING):
0. Deduplicate: compare against findings/README.md and skip if it matches an existing finding signature, root cause, or impact family.
1. Reproduce: From ${INPUT_NOTES} and ${INPUT_POC}, create a minimal coded PoC or deterministic trace that steadily reproduces the impact.
2. Copy the reproducible PoC to findings/finding_<timestamp>_agent${AGENT_ID}.t.sol, findings/finding_<timestamp>_agent${AGENT_ID}.test.js, or the native extension for the repo.
3. Copy supporting notes to findings/finding_<timestamp>_agent${AGENT_ID}.md.
4. Append a record to findings/README.md using flock -x locks/findings.lock, including severity estimate, target, impact, root cause, top code location, reproduction command, duplicate signature, shard focus, and confidence.
5. If the finding appears High or Medium, write a concise report draft in reports/report_<timestamp>_agent${AGENT_ID}.md with Code4rena-style sections: Summary, Vulnerability Details, Impact, Proof of Concept, Tools Used, Recommended Mitigation.
