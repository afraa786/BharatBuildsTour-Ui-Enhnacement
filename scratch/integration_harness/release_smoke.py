import os
import subprocess
import sys


def run_command(cmd, name):
    print(f"--- Running {name} ---")
    result = subprocess.run(cmd, shell=True, check=False)
    if result.returncode == 0:
        print(f"[{name}] PASS\n")
        return True
    else:
        print(f"[{name}] FAIL\n")
        return False


def smoke_run():
    success = True

    # Fixtures validator
    success &= run_command(
        "PYTHONPATH=$PWD/server:$PWD/scratch/integration_harness server/.venv/bin/python scratch/integration_harness/frontend/fixtures_generator.py",
        "Frontend Fixture Validator",
    )

    # Offline Journey
    success &= run_command(
        "PYTHONPATH=$PWD/server:$PWD/scratch/integration_harness server/.venv/bin/python scratch/integration_harness/run_journey.py --offline",
        "Offline Journey",
    )

    # Failure Journeys
    success &= run_command(
        "PYTHONPATH=$PWD/server:$PWD/scratch/integration_harness server/.venv/bin/python scratch/integration_harness/run_failures.py",
        "Failure Journeys",
    )

    # Run tests
    success &= run_command(
        "PYTHONPATH=$PWD/server:$PWD/scratch/integration_harness server/.venv/bin/pytest -v scratch/integration_harness/tests/",
        "Harness Tests",
    )

    if os.environ.get("STOCKAWARE_HTTP_ACCEPTANCE") == "1":
        success &= run_command(
            "PYTHONPATH=$PWD/server:$PWD/scratch/integration_harness "
            "server/.venv/bin/python scratch/integration_harness/run_journey.py --http",
            "HTTP Acceptance",
        )
    else:
        print("[HTTP Acceptance] SKIP / CONFIG_NOT_AVAILABLE\n")

    print("\n=== SMOKE RUNNER RESULT ===")
    if success:
        print("PASS")
        return 0
    else:
        print("FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(smoke_run())
