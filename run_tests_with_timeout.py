#!/usr/bin/env python3
"""
Test runner with comprehensive timeout handling and coverage reporting

This script runs all tests with proper timeout handling and generates
detailed coverage reports for the FeatureFlagsHQ SDK.
"""

import sys
import subprocess
import time
import os
from pathlib import Path


def run_command_with_timeout(cmd, timeout_seconds=300):
    """Run a command with timeout"""
    print(f"Running: {' '.join(cmd)}")
    print(f"Timeout: {timeout_seconds} seconds")
    
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=Path(__file__).parent
        )
        
        elapsed = time.time() - start_time
        print(f"Completed in {elapsed:.2f} seconds")
        
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        return result.returncode == 0, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"Command timed out after {elapsed:.2f} seconds")
        return False, "", f"Command timed out after {timeout_seconds} seconds"
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"Command failed after {elapsed:.2f} seconds: {e}")
        return False, "", str(e)


def main():
    """Main test runner"""
    print("=" * 60)
    print("FeatureFlagsHQ SDK Test Suite with Timeout Handling")
    print("=" * 60)
    
    # Ensure we're in the right directory
    os.chdir(Path(__file__).parent)
    
    # Test scenarios to run
    test_scenarios = [
        {
            "name": "Unit Tests (Fast)",
            "cmd": [
                sys.executable, "-m", "pytest", 
                "tests/unit/", 
                "-v", 
                "--tb=short",
                "-x"  # Stop on first failure for fast feedback
            ],
            "timeout": 60
        },
        {
            "name": "Security Tests",
            "cmd": [
                sys.executable, "-m", "pytest", 
                "tests/unit/test_security.py",
                "tests/unit/test_network_errors.py", 
                "-v", 
                "--tb=short"
            ],
            "timeout": 45
        },
        {
            "name": "Integration Tests (Limited)",
            "cmd": [
                sys.executable, "-m", "pytest", 
                "tests/integration/", 
                "-v", 
                "--tb=short",
                "-k", "not concurrent"  # Skip slow concurrent tests
            ],
            "timeout": 120
        },
        {
            "name": "Coverage Report (Fast)",
            "cmd": [
                sys.executable, "-m", "pytest", 
                "tests/unit/",
                "--cov=featureflagshq", 
                "--cov-report=term-missing",
                "--cov-report=html",
                "--tb=no",  # No traceback for faster execution
                "-q"  # Quiet mode
            ],
            "timeout": 90
        }
    ]
    
    results = []
    
    for scenario in test_scenarios:
        print(f"\n{'-' * 50}")
        print(f"Running: {scenario['name']}")
        print(f"{'-' * 50}")
        
        success, stdout, stderr = run_command_with_timeout(
            scenario['cmd'], 
            scenario['timeout']
        )
        
        results.append({
            "name": scenario['name'],
            "success": success,
            "stdout": stdout,
            "stderr": stderr
        })
        
        if not success:
            print(f"FAIL - {scenario['name']} FAILED")
            if "timeout" in stderr.lower():
                print("TIMEOUT - Test suite exceeded timeout limit")
        else:
            print(f"PASS - {scenario['name']} PASSED")
    
    # Summary
    print(f"\n{'=' * 60}")
    print("TEST SUMMARY")
    print(f"{'=' * 60}")
    
    passed = sum(1 for r in results if r['success'])
    total = len(results)
    
    for result in results:
        status = "PASS" if result['success'] else "FAIL"
        print(f"{status} - {result['name']}")
        
        if not result['success'] and result['stderr']:
            # Show brief error info
            error_lines = result['stderr'].split('\n')[:3]
            for line in error_lines:
                if line.strip():
                    print(f"   Error: {line.strip()}")
    
    print(f"\nResults: {passed}/{total} test scenarios passed")
    
    # Generate final coverage summary if coverage was run
    coverage_result = next((r for r in results if "Coverage" in r['name']), None)
    if coverage_result and coverage_result['success']:
        print(f"\nCoverage report generated in htmlcov/index.html")
    
    # Exit with appropriate code
    if passed == total:
        print("\nAll test scenarios completed successfully!")
        sys.exit(0)
    else:
        print(f"\n{total - passed} test scenarios failed or timed out")
        sys.exit(1)


if __name__ == "__main__":
    main()