# Guardrailed Agent Harness

> Step-by-step guide: **[Build a Guardrailed Agent Harness for Safe AI Delegation](https://erness.dev/tutorials/guardrailed-agent-harness/)**. The guide explains the why behind each file, the safety notes and what went wrong along the way.

> **Teaching Example Disclaimer:** This repository provides a simplified, self-contained Python demonstration of the guardrailed CLI delegation pattern. It uses a local `state.json` file rather than live production servers or home automation hardware. Adapt the recipes and tools to your specific environment.

## Overview

Giving an AI agent unrestricted command-line access to system administration tools introduces serious risks: hallucinations, hangs on background processes, and accidental disruption of critical power infrastructure.

This project demonstrates how to build a guardrailed execution harness that enforces:
1. **Fixed Recipe Templates:** The LLM only supplies parameters; the tool handles logic.
2. **Protected Entities:** Critical devices (e.g. server power plugs) are hardcoded as untouchable.
3. **Pre-Execution Backups:** State is snapshotted before any command runs.
4. **Synchronous Foreground Execution:** Commands run with strict timeouts, avoiding hung sessions.
5. **Deterministic Post-Checks:** Before-and-after state comparisons catch hallucinated successes.
6. **Audit Trail & Trust Policy:** Every run is recorded with a pending-review status for human auditing.

## Requirements

- Python 3.8 or newer (standard library only, no pip dependencies)
- Linux or Unix-compatible shell

## Repository Files

- `harness.py`: The CLI runner with recipe definitions, guardrails, post-checks, and audit logging.
- `mock_agent.py`: A simulated agent script that applies valid recipe changes to `state.json`.
- `state.json`: A sample system state representing registered devices and rules.

## Quickstart

### 1. Test Hallucination Detection (Default Echo Stub)
Run a recipe using the default harmless echo command. The agent outputs success text, but because `state.json` is not modified, the deterministic post-check immediately flags the failure:
```bash
python3 harness.py run pair-device --id light.kitchen_ceiling --type light
```

### 2. Test Verified Execution (Mock Agent)
Run the same recipe using `mock_agent.py`. The mock agent applies the requested change, and the post-check confirms the state mutation:
```bash
python3 harness.py run pair-device --id light.kitchen_ceiling --type light --agent-cmd "python3 mock_agent.py"
```

### 3. Create a Verified Automation Rule
Link an existing sensor to a light using the `create-rule` recipe:
```bash
python3 harness.py run create-rule --id rule_kitchen_presence --sensor sensor.stairs_top_presence --target-light light.stairs_light --agent-cmd "python3 mock_agent.py"
```

### 4. Test Protected Entity Guardrails
Attempting to modify a protected entity aborts immediately before any agent command is invoked:
```bash
python3 harness.py run pair-device --id switch.server_power_plug --type smart_plug
```

### 5. Inspect the Audit Log
View all past executions and their review status:
```bash
python3 harness.py history
```

## Looking for the real tool?

This repository is a small teaching example of the pattern. The tool I actually use every day is [delegar-gemini](https://github.com/ernessx/delegar-gemini).
