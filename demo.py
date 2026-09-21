# Roll Number: evernorth-aai-1177619
import argparse
from agent import run_capability

def run_all():
    # Run all required capabilities in order
    caps = ["R1", "R2", "R3", "R4", "R5", "R6", "X1", "X2", "X3"]
    for cap in caps:
        print(f"\n=== Running {cap} ===")
        run_capability(cap)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="InboxHero demo runner")
    parser.add_argument("--cap", type=str, help="Capability ID (R1–R6, X1–X3)")
    parser.add_argument("--all", action="store_true", help="Run all capabilities in sequence")
    args = parser.parse_args()

    if args.all:
        run_all()
    elif args.cap:
        run_capability(args.cap)
    else:
        print("Usage: python demo.py --cap R1")
