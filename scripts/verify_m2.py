"""Run M1 regression checks plus the M2 offline candidate-retention experiment."""

from verify_m1 import main

if __name__ == "__main__":
    raise SystemExit(main(stage="m2"))
