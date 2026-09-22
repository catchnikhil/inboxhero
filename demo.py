#!/usr/bin/env python3
"""
demo.py

Driver script to exercise the inbox agent capabilities for local testing.
Usage examples:
  python demo.py --cap R1
  python demo.py --cap R2 --msg m008
  python demo.py --cap X3 --dry-run
  python demo.py --all
"""

import argparse
import sys
import traceback

from config import Config
import google.generativeai as genai

# Validate config and configure Gemini
Config.validate()
genai.configure(api_key=Config.GEMINI_API_KEY)

# Import agent capabilities
try:
    import agent  # expects agent.py in same directory or PYTHONPATH
except Exception as e:
    print("Failed to import agent module. Make sure agent.py is available and importable.")
    print(e)
    sys.exit(2)


def _safe_call(func, *args, **kwargs):
    """Call a capability function and catch exceptions so demo can continue."""
    name = getattr(func, "__name__", str(func))
    try:
        print(f"\n=== Running {name} ===")
        func(*args, **kwargs)
        print(f"=== Finished {name} ===\n")
    except AssertionError as ae:
        print(f"[ASSERTION FAILED] {name}: {ae}")
        traceback.print_exc()
    except Exception as exc:
        print(f"[ERROR] Exception while running {name}: {exc}")
        traceback.print_exc()


def run_all(dry_run: bool):
    """
    Run a safe sequence of capabilities for demonstration.
    R3 and X3 are run in dry-run mode to avoid irreversible actions.
    """
    _safe_call(agent.run_r1_zero_inbox)
    _safe_call(agent.run_r5_hostile_inbox)
    _safe_call(agent.run_r6_dashboard)
    _safe_call(agent.run_x2_morning_digest)
    _safe_call(agent.run_x1_followup_tracker)
    _safe_call(agent.run_r3_gate, dry_run, "m008")
    _safe_call(agent.run_x3_conflict_detection, dry_run)


def main():
    parser = argparse.ArgumentParser(description="Demo runner for inbox agent capabilities")
    parser.add_argument("--cap", type=str, help="Capability to run (e.g., R1, R2, R3, R4, R5, R6, X1, X2, X3)")
    parser.add_argument("--msg", type=str, default="m008", help="Target message ID for R2/R3/R4")
    parser.add_argument("--dry-run", action="store_true", help="Run without executing irreversible actions")
    parser.add_argument("--all", action="store_true", help="Run a safe demo sequence of capabilities")
    args = parser.parse_args()

    cap_map = {
        "R1": agent.run_r1_zero_inbox,
        "R2": lambda: agent.run_r2_grounded_reply(args.msg),
        "R3": lambda: agent.run_r3_gate(args.dry_run, args.msg),
        "R4": lambda: agent.run_r4_persistent_preference(args.msg),
        "R5": agent.run_r5_hostile_inbox,
        "R6": agent.run_r6_dashboard,
        "X1": agent.run_x1_followup_tracker,
        "X2": agent.run_x2_morning_digest,
        "X3": lambda: agent.run_x3_conflict_detection(is_dry_run=args.dry_run),
    }

    if args.all:
        run_all(args.dry_run)
        return

    if not args.cap:
        print("Please specify a capability with --cap or use --all to run the demo sequence.")
        return

    cap = args.cap.strip().upper()
    if cap not in cap_map:
        print(f"Unknown capability '{cap}'. Valid options: {', '.join(sorted(cap_map.keys()))}")
        return

    func = cap_map[cap]
    _safe_call(func)


if __name__ == "__main__":
    main()
