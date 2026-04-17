# ACP Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Repair the ACP client plugin's broken runtime behavior, expose the tools declared in the plugin manifest, and add runnable regression tests for the fixed behavior.

**Architecture:** Keep the current `protocol -> transport -> tools -> hooks` split. Add focused unit-style regression tests around `tools.register`, dispatch/result lifecycle, cancel behavior, and hook injection so the fixes are enforced without depending on external ACP workers.

**Tech Stack:** Python 3 stdlib (`unittest`, `unittest.mock`), Hermes plugin entrypoints, in-memory session manager.

---

### Task 1: Add regression tests for plugin registration and hook injection

**Files:**
- Create: `tests/test_regressions.py`
- Test: `tests/test_regressions.py`

**Step 1: Write the failing test**

Add tests that assert:
- `register(ctx)` exposes all tools declared in `plugin.yaml`
- repeated `pre_llm_call_hook()` calls do not accumulate duplicate ACP system messages

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_regressions.py' -v`
Expected: FAIL because `register()` only registers three tools and hook injection duplicates system messages.

**Step 3: Write minimal implementation**

Update plugin registration and hook injection logic only enough to satisfy the tests.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -p 'test_regressions.py' -v`
Expected: PASS for registration and hook tests.

### Task 2: Add regression tests for dispatch/result lifecycle

**Files:**
- Modify: `tests/test_regressions.py`
- Test: `tests/test_regressions.py`

**Step 1: Write the failing test**

Add tests that assert:
- `acp_dispatch()` stores the worker result when `session/prompt` returns a final result
- completed sessions become retrievable through `acp_result()`
- failed prompt responses mark the session failed

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_regressions.py' -v`
Expected: FAIL because dispatch currently leaves successful sessions in `running`.

**Step 3: Write minimal implementation**

Update `tools.py` notification/result handling so direct prompt responses populate session result and terminal state consistently.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -p 'test_regressions.py' -v`
Expected: PASS for dispatch/result lifecycle tests.

### Task 3: Tighten cancel semantics and manifest consistency

**Files:**
- Modify: `tests/test_regressions.py`
- Modify: `tools.py`
- Modify: `__init__.py`
- Modify: `plugin.yaml`

**Step 1: Write the failing test**

Add tests that assert:
- `acp_cancel()` reports whether cancellation was propagated to the transport
- if transport cancel is unavailable, response clearly reports local-only cancellation

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_regressions.py' -v`
Expected: FAIL because cancel currently only flips in-memory state without surfacing that limitation.

**Step 3: Write minimal implementation**

Teach tools to attempt transport-level cancellation when available, otherwise return explicit `cancellation_scope: local_only`. Keep manifest and registration list aligned.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -p 'test_regressions.py' -v`
Expected: PASS for cancellation and registration behavior.

### Task 4: Update docs to match shipped behavior

**Files:**
- Modify: `README.md`
- Modify: `src/main.py`
- Modify: `acp/__init__.py`
- Modify: `acp/protocol.py`

**Step 1: Write the failing test**

No code test. Use consistency checks from manual review:
- one project version
- README tool list matches actual registered tools
- CLI examples use current parameter names

**Step 2: Run verification**

Run: `rg -n "0\\.1\\.0|0\\.2\\.0|0\\.2\\.1|1\\.0\\.0|session-id|session_id" README.md src/main.py acp/__init__.py acp/protocol.py plugin.yaml __init__.py`
Expected: shows drift before edits.

**Step 3: Write minimal implementation**

Normalize version references and README examples to current code.

**Step 4: Run verification**

Run the same `rg` command.
Expected: only the intended current version and parameter forms remain.

### Task 5: Final verification

**Files:**
- Test: `tests/test_regressions.py`

**Step 1: Run targeted regression suite**

Run: `python3 -m unittest discover -s tests -p 'test_regressions.py' -v`
Expected: PASS.

**Step 2: Run syntax verification**

Run: `python3 -m compileall acp tools.py schemas.py src/main.py __init__.py`
Expected: PASS with no syntax errors.
