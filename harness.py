#!/usr/bin/env python3
"""Simplified Guardrailed CLI Harness for LLM-Driven System Administration.

Demonstrates a safe delegation pattern:
1. Narrow recipes with strict parameter validation.
2. Protected entities that can never be modified.
3. Automatic pre-run state backups.
4. Synchronous foreground command execution with timeouts.
5. Deterministic post-checks comparing actual before/after state.
6. Audit logging with human-in-the-loop pending-review status.
"""

import argparse
from datetime import datetime, timezone
import json
import os
import re
import shutil
import subprocess
import sys

STATE_FILE = "state.json"
BACKUP_FILE = "state.json.bak"
HISTORY_FILE = "history.json"

PROTECTED_ENTITIES = {
    "switch.server_power_plug",
    "switch.workstation_power_plug",
}


def load_state(path=STATE_FILE):
  if not os.path.exists(path):
    return {"devices": {}, "rules": {}}
  with open(path, "r", encoding="utf-8") as f:
    return json.load(f)


def create_backup():
  if os.path.exists(STATE_FILE):
    shutil.copy2(STATE_FILE, BACKUP_FILE)


def restore_backup():
  if os.path.exists(BACKUP_FILE):
    shutil.copy2(BACKUP_FILE, STATE_FILE)


def validate_identifier(name):
  if not re.match(r"^[a-zA-Z0-9_\.]+$", name):
    raise ValueError(
        f"Invalid name '{name}': only alphanumeric characters, underscores, and dots are allowed."
    )
  if name in PROTECTED_ENTITIES:
    raise ValueError(
        f"Security violation: '{name}' is a protected entity and cannot be modified."
    )


def recipe_pair_device(params, current_state):
  dev_id = params.get("id")
  dev_type = params.get("type", "light")
  if not dev_id:
    raise ValueError("Missing required parameter: --id")
  validate_identifier(dev_id)
  if dev_id in current_state.get("devices", {}):
    raise ValueError(f"Device '{dev_id}' already exists in state.")
  return (
      f"TASK: Register a new device with ID '{dev_id}' of type '{dev_type}'.\n"
      f"Set initial status to 'online'. Do not modify any other devices."
  )


def check_pair_device(before_state, after_state, params):
  dev_id = params["id"]
  before_devs = before_state.get("devices", {})
  after_devs = after_state.get("devices", {})
  added = set(after_devs.keys()) - set(before_devs.keys())
  if added != {dev_id}:
    return (
        False,
        f"Expected exactly device '{dev_id}' to be added, but found {list(added)}.",
    )
  for k, v in before_devs.items():
    if k not in after_devs:
      return False, f"Preexisting device '{k}' was deleted."
    if after_devs[k] != v:
      return False, f"Preexisting device '{k}' was unexpectedly modified."
  for p in PROTECTED_ENTITIES:
    if p in after_devs and after_devs[p] != before_devs.get(p):
      return False, f"Protected device '{p}' was altered!"
  return True, f"Device '{dev_id}' verified successfully in state."


def recipe_create_rule(params, current_state):
  rule_id = params.get("id")
  sensor = params.get("sensor")
  target_light = params.get("target_light")
  if not rule_id or not sensor or not target_light:
    raise ValueError(
        "Missing parameters: --id, --sensor, and --target-light are all required."
    )
  for item in (rule_id, sensor, target_light):
    validate_identifier(item)
  devices = current_state.get("devices", {})
  if sensor not in devices:
    raise ValueError(f"Sensor '{sensor}' does not exist in devices.")
  if target_light not in devices:
    raise ValueError(f"Target light '{target_light}' does not exist in devices.")
  if rule_id in current_state.get("rules", {}):
    raise ValueError(f"Rule '{rule_id}' already exists in state.")
  return (
      f"TASK: Create automation rule '{rule_id}' linking trigger sensor '{sensor}' "
      f"to target '{target_light}'. Ensure rule is enabled with 'enabled': true."
  )


def check_create_rule(before_state, after_state, params):
  rule_id = params["id"]
  sensor = params["sensor"]
  target_light = params["target_light"]
  before_rules = before_state.get("rules", {})
  after_rules = after_state.get("rules", {})
  added = set(after_rules.keys()) - set(before_rules.keys())
  if added != {rule_id}:
    return (
        False,
        f"Expected exactly rule '{rule_id}' to be added, but found {list(added)}.",
    )
  rule = after_rules[rule_id]
  if rule.get("trigger") != sensor:
    return False, f"Rule trigger is '{rule.get('trigger')}', expected '{sensor}'."
  if rule.get("target") != target_light:
    return False, f"Rule target is '{rule.get('target')}', expected '{target_light}'."
  if not rule.get("enabled", False):
    return False, "Rule was created but is not enabled."
  for k, v in before_rules.items():
    if k not in after_rules or after_rules[k] != v:
      return False, f"Preexisting rule '{k}' was altered or deleted."
  return True, f"Rule '{rule_id}' verified successfully in state."


RECIPES = {
    "pair-device": {
        "builder": recipe_pair_device,
        "checker": check_pair_device,
    },
    "create-rule": {
        "builder": recipe_create_rule,
        "checker": check_create_rule,
    },
}


def run_agent_command(agent_cmd, prompt, recipe_name, params):
  env = os.environ.copy()
  env["HARNESS_RECIPE"] = recipe_name
  env["HARNESS_PARAMS_JSON"] = json.dumps(params)
  env["HARNESS_PROMPT"] = prompt
  try:
    proc = subprocess.run(
        agent_cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    output = (proc.stdout + "\n" + proc.stderr).strip()
    return proc.returncode, output
  except subprocess.TimeoutExpired:
    return -1, "Command timed out after 15 seconds."
  except Exception as e:
    return -1, f"Execution failed: {e}"


def log_history(entry):
  history = []
  if os.path.exists(HISTORY_FILE):
    try:
      with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    except Exception:
      history = []
  history.append(entry)
  with open(HISTORY_FILE, "w", encoding="utf-8") as f:
    json.dump(history, f, indent=2)


def main():
  parser = argparse.ArgumentParser(
      description="Guardrailed CLI Harness for LLM-Driven System Administration"
  )
  subparsers = parser.add_subparsers(dest="command", required=True)

  run_p = subparsers.add_parser("run", help="Run a guardrailed recipe")
  run_p.add_argument("recipe", choices=list(RECIPES.keys()), help="Recipe name")
  run_p.add_argument("--id", required=True, help="Identifier for device or rule")
  run_p.add_argument("--type", default="light", help="Device type (pair-device)")
  run_p.add_argument("--sensor", help="Trigger sensor entity ID (create-rule)")
  run_p.add_argument("--target-light", help="Target light entity ID (create-rule)")
  run_p.add_argument(
      "--agent-cmd",
      default='echo "Agent output: Task completed successfully."',
      help="Agent command to execute (defaults to harmless echo stub)",
  )

  subparsers.add_parser("history", help="Show execution audit log")
  args = parser.parse_args()

  if args.command == "history":
    if not os.path.exists(HISTORY_FILE):
      print("No execution history found.")
      return
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
      history = json.load(f)
    print(f"{'TIMESTAMP':<25} {'RECIPE':<15} {'STATUS':<25} {'DETAILS'}")
    print("-" * 80)
    for entry in history:
      ts = entry.get("timestamp", "")[:19]
      rec = entry.get("recipe", "")
      st = entry.get("status", "")
      det = entry.get("check_message", "")
      print(f"{ts:<25} {rec:<15} {st:<25} {det}")
    return

  if args.command == "run":
    recipe_name = args.recipe
    recipe_conf = RECIPES[recipe_name]
    params = {
        "id": args.id,
        "type": args.type,
        "sensor": args.sensor,
        "target_light": args.target_light,
    }
    params = {k: v for k, v in params.items() if v is not None}

    before_state = load_state()
    try:
      prompt = recipe_conf["builder"](params, before_state)
    except Exception as e:
      print(f"[PRE-CHECK ERROR] {e}")
      sys.exit(1)

    print(f"[*] Recipe: {recipe_name}")
    print(f"[*] Prompt generated:\n    {prompt}")
    print(f"[*] Executing agent command: {args.agent_cmd}")

    create_backup()
    code, output = run_agent_command(args.agent_cmd, prompt, recipe_name, params)
    print(f"[*] Agent exit code: {code}")
    print(f"[*] Agent output:\n    {output}")

    after_state = load_state()
    check_passed, check_msg = recipe_conf["checker"](before_state, after_state, params)
    status = "SUCCESS (Pending Review)" if check_passed else "FAILED"

    print(f"[*] Post-check result: {status}")
    print(f"    Message: {check_msg}")

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "recipe": recipe_name,
        "params": params,
        "prompt": prompt,
        "agent_cmd": args.agent_cmd,
        "agent_output": output,
        "check_passed": check_passed,
        "check_message": check_msg,
        "status": status,
        "reviewed": False,
    }
    log_history(log_entry)

    if not check_passed:
      print("[!] Warning: Checks failed. Restoring previous state snapshot.")
      restore_backup()
      sys.exit(1)
    else:
      print("[+] Success: Operation verified and logged for manual review.")


if __name__ == "__main__":
  main()
