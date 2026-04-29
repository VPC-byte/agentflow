Here is the prompt after several evolutions (ofc there are also evolutions on tools and MAS graph): 

Chromium is very well audited and vulnerabilities can only occur very deep in the code. Do not do surface work! You can always enable any stable blink feature (e.g., MachineLearningNeuralNetwork) and use reasonable flags that are going to be used in production / release.  

Your target component is ${TARGET}.

STRICT CONSTRAINTS & DEFINITION OF A CRASH:
1. DO NOT edit the Chromium source code.
2. DO NOT write, compile, or run C++ unit tests.
3. FOCUS ONLY ON MEMORY BUGS in the C++ engine (Blink, V8, IPC, Skia, media, etc.). blink/modules/ai is out of scope. 
4. DEFINITION OF A CRASH: A JavaScript exception is NOT A CRASH.
5. You MUST ONLY log a crash if execution shows one of:
   - AddressSanitizer (ASAN) report
   - UndefinedBehaviorSanitizer (UBSAN) report relevant to memory safety
   - CHECK/DCHECK/FATAL assertion-only crashes are out of scope and MUST NOT be documented.
6. UBSAN NOISE FILTER: Ignore non-memory UB only reports (pure signed overflow, benign shifts, etc.) unless accompanied by concrete memory corruption symptoms.
7. MULTI-PROCESS AWARENESS: Chromium is multi-process. Renderer crashes commonly appear as Playwright exceptions while the sanitizer trace appears in stderr.
8. PROCESS MODEL REQUIREMENT: DO NOT use p.chromium.launch() for the target browser. The script must start Chromium as an external subprocess with a RANDOM CDP port and then connect via Playwright CDP.
9. REPRO CHECK: Before logging a crash, rerun at least once to confirm reproducibility and collect the clearest stack trace.
10. GDB USAGE: Because Chromium is externally launched, attach gdb to the launched browser PID or child renderer PID for reachability checks only when necessary. DO NOT use gdb if you don't need it. DO NOT use gdb to debug after crash is confirmed.
11. USE THE PROVIDED HELPERS: Use ${AGENT_UTILS} and start from ${AGENT_TEMPLATE}. Do NOT re-implement Chromium launch/CDP plumbing unless helper behavior is insufficient.
12. DO NOT STOP UNTIL ${TARGET_TRUE_CRASHES} TRUE C++ CRASHES ARE FOUND.
13. DO NOT EXPLORE MODULES ALREADY DOCUMENTED TO BE CRASHING IN crashes/README.md. Human engineers need to fix them first! Even though you many find another way to crash it, it is useless.
14. OWNERSHIP RULE: If you notice a new crashes/README.md entry (especially one added by another agent), do NOT reproduce it, extend it, or further investigate that crash family. It is not your obligation; move to a different component immediately.
15. DO NOT read / attempt to read other agents' directory. It is none of your business. 
16. For deduplication, simply DO NOT analyze modules that are already crashing. You can get the module name from craches/README.md directly. DO NOT read/analyze other agents' work!

WORKFLOW:
Step 1: PICK TARGET - Select a random component in ${CHROMIUM_SOURCE}.
Step 2: GATHER KNOWLEDGE - Read docs/ for existing component notes and docs/global_lessons.md to avoid duplicate effort.
  - While working, re-check crashes/README.md before any repro/logging action. If a matching or newly-added crash family appears, stop that line of work immediately and pick a new target.
Step 3: EXPLORATION LOOP -
   a. INSPECT: Audit target C++ paths for UAF/OOB/type confusion/lifetime bugs.
   b. GENERATE PAYLOAD: Write an HTML+JS trigger to ${INPUT_HTML}.
   c. GENERATE ORCHESTRATOR: Start from ${AGENT_TEMPLATE} and write ${INPUT_PY} using ${AGENT_UTILS}.
      Minimal API to use:
      - from utils import start_browser
      - with start_browser(CHROMIUM_PATH, log_dir=str(AGENT_DIR)) as session:
      - session.open_file(INPUT_HTML)
      - page = session.page
      - session.chrome_pid and session.renderer_pids() for GDB target selection
      The helper already handles: random CDP port, external Chromium launch, Playwright connect_over_cdp, ASAN startup ODR-noise suppression, debugger-attach-friendly process setup, and cleanup.
   d. EXECUTE: Run python3 ${INPUT_PY} 2>&1 and analyze stderr/stdout.
   e. VERIFY: Look only for ASAN or memory-UBSAN signatures. CHECK/DCHECK/FATAL assertion-only crashes and plain segfault/signal traces without sanitizer-backed memory evidence are out of scope and must not be logged. MiraclePtr-protected bugs are out of scope (i.e., for in-scope crashes, you need to see 'MiraclePtr Status: NOT PROTECTED'), unless you can show exploitation of a BRP-protected use-after-free. Ignore plain JS errors or renderer crash or page crash, unless you can escalate to a full browser crash.
   * Repeat until component is exhausted or a TRUE crash is found.
   * It is not your job to analyze the root cause or debug the crash. 
Step 4: DOCUMENT COMPONENT - If no crash, write findings to docs/<short_name>.md using locking, for example:
   flock -x locks/docs.lock -c 'cat <<EOF > docs/blink_layout_lessons.md
   [detailed findings]
   EOF'
Step 5: LOG GENERAL LESSONS - Append reusable Chromium/Playwright execution lessons to docs/global_lessons.md with flock locking, only if you believe these lessons are important and new and unique. 
Step 6: PICK NEW TARGET - Return to Step 1.

CRASH HANDLING (ONLY AFTER TRUE CRASH):
0. Deduplicate: compare against crashes/README.md and skip if it matches an existing crash signature.
1. Reproduce: From ${INPUT_HTML} and ${INPUT_PY} create a python script and a HTML that can steadily reproduce the crash.  
1. Copy the reproducible HTML file to crashes/crash_<timestamp>_agent${AGENT_ID}.html
2. Copy the reproducible Python script to crashes/crash_<timestamp>_agent${AGENT_ID}.py
3. Append a record to crashes/README.md using flock -x locks/crashes.lock, including crash type and top stack frame.
