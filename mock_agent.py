#!/usr/bin/env python3
"""Simplified mock agent simulating tool execution for the harness.

Reads recipe parameters passed by harness.py via environment variables and
safely updates state.json to simulate an authorized tool action.
"""

import json
import os
import sys

STATE_FILE = "state.json"


def main():
  recipe = os.environ.get("HARNESS_RECIPE")
  params_raw = os.environ.get("HARNESS_PARAMS_JSON", "{}")

  try:
    params = json.loads(params_raw)
  except json.JSONDecodeError:
    print("Mock Agent Error: Invalid parameters JSON.", file=sys.stderr)
    sys.exit(1)

  if not os.path.exists(STATE_FILE):
    print(f"Mock Agent Error: State file '{STATE_FILE}' not found.", file=sys.stderr)
    sys.exit(1)

  with open(STATE_FILE, "r", encoding="utf-8") as f:
    state = json.load(f)

  if recipe == "pair-device":
    dev_id = params.get("id")
    dev_type = params.get("type", "light")
    state.setdefault("devices", {})[dev_id] = {
        "type": dev_type,
        "status": "online",
    }
    print(f"Mock Agent: Registered device '{dev_id}' of type '{dev_type}'.")

  elif recipe == "create-rule":
    rule_id = params.get("id")
    sensor = params.get("sensor")
    target = params.get("target_light")
    state.setdefault("rules", {})[rule_id] = {
        "trigger": sensor,
        "target": target,
        "enabled": True,
    }
    print(
        f"Mock Agent: Created automation rule '{rule_id}' ({sensor} -> {target})."
    )

  else:
    print(f"Mock Agent Error: Unknown recipe '{recipe}'.", file=sys.stderr)
    sys.exit(1)

  with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2)


if __name__ == "__main__":
  main()
