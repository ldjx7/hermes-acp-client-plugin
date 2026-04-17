# Service Repository Worker Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the ACP plugin internals so tool handlers become thin entrypoints and the runtime logic lives in services, repositories, and worker adapters.

**Architecture:** Keep the Hermes plugin interface unchanged while moving orchestration out of `tools.py`. Introduce a repository abstraction over the in-memory session store, a worker adapter registry for command/capability lookups, and service objects that own dispatch, progress, result, and cancel flows.

**Tech Stack:** Python 3 stdlib, existing ACP protocol/transport layer, `unittest`, `unittest.mock`.

---

### Task 1: Add failing tests for service delegation and worker registry

**Files:**
- Modify: `tests/test_regressions.py`
- Test: `tests/test_regressions.py`

**Step 1: Write the failing test**

Add tests asserting:
- `tools.acp_dispatch()` delegates to a dispatch service getter
- `tools.acp_progress()` delegates to a progress service getter
- `tools.acp_result()` delegates to a result service getter
- a worker registry exists and `acp.transport.get_worker_command()` reads command data from it

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_regressions.py' -v`
Expected: FAIL because services and worker registry do not exist yet and tool handlers still contain orchestration logic.

**Step 3: Write minimal implementation**

Create the service and worker registry modules, then update `tools.py` and `acp/transport.py` to use them.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -p 'test_regressions.py' -v`
Expected: PASS for the new delegation and registry tests.

### Task 2: Introduce repository abstraction over session state

**Files:**
- Create: `repositories/__init__.py`
- Create: `repositories/session_repository.py`
- Create: `repositories/memory_session_repository.py`
- Modify: `acp/hooks.py`
- Test: `tests/test_regressions.py`

**Step 1: Write the failing test**

Extend tests to require the new repository package and ensure hook behavior still works through the abstraction.

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_regressions.py' -v`
Expected: FAIL until repository modules exist and hooks consume them.

**Step 3: Write minimal implementation**

Wrap `SessionManager` with `MemorySessionRepository`, expose a singleton getter, and update hooks/services to use the repository instead of touching the manager directly where practical.

**Step 4: Run test to verify it passes**

Run the same command.
Expected: PASS.

### Task 3: Move orchestration logic into services

**Files:**
- Create: `services/__init__.py`
- Create: `services/dispatch_service.py`
- Create: `services/progress_service.py`
- Create: `services/result_service.py`
- Modify: `tools.py`
- Test: `tests/test_regressions.py`

**Step 1: Write the failing test**

Use the delegation tests from Task 1 and existing dispatch/result/cancel regression tests as the failing net.

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_regressions.py' -v`
Expected: FAIL until services implement the same behavior as the old tool handlers.

**Step 3: Write minimal implementation**

Move:
- transport initialization + notification handling into `DispatchService`
- progress/list/cleanup into `ProgressService`
- result/cancel into `ResultService`

Keep JSON response format stable for callers.

**Step 4: Run test to verify it passes**

Run the same command.
Expected: PASS.

### Task 4: Add worker adapter registry

**Files:**
- Create: `workers/__init__.py`
- Create: `workers/base.py`
- Create: `workers/registry.py`
- Modify: `acp/transport.py`
- Test: `tests/test_regressions.py`

**Step 1: Write the failing test**

Use the worker registry tests from Task 1.

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_regressions.py' -v`
Expected: FAIL until transport resolves command data from adapters.

**Step 3: Write minimal implementation**

Add per-worker command/capability definitions and route `get_worker_command()` through the registry.

**Step 4: Run test to verify it passes**

Run the same command.
Expected: PASS.

### Task 5: Final verification and docs touch-up

**Files:**
- Modify: `README.md`
- Test: `tests/test_regressions.py`

**Step 1: Run targeted regression suite**

Run: `python3 -m unittest discover -s tests -p 'test_regressions.py' -v`
Expected: PASS.

**Step 2: Run syntax verification**

Run: `python3 -m compileall acp tools.py schemas.py src/main.py __init__.py repositories services workers tests/test_regressions.py`
Expected: PASS with no syntax errors.
