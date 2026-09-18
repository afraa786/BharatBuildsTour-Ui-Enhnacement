import json
import os
import pytest
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALIDATOR_SCRIPT = os.path.join(BASE_DIR, 'validator.py')

def test_run_validator():
    """Ensure that the validator script runs without raising an error."""
    # The validator itself contains all the response safety checks.
    # Running it as a test ensures we don't regress.
    result = subprocess.run([sys.executable, VALIDATOR_SCRIPT], capture_output=True, text=True)
    assert result.returncode == 0, f"Validator failed with output:\n{result.stdout}\n{result.stderr}"
