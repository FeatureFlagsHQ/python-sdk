#!/usr/bin/env python3
"""
Test script to verify the fix for single flag retrieval blocking issue.
This script tests that the get() method doesn't hang even when initialization fails.
"""

import time
from unittest.mock import patch, Mock
from featureflagshq import FeatureFlagsHQSDK
from featureflagshq.models import FeatureFlagsHQFlag, FeatureFlagsHQRollout


def test_get_method_with_hanging_initialization():
    """Test that get() method doesn't hang when initialization takes too long"""
    print("Testing get() method with simulated hanging initialization...")
    
    # Mock _fetch_flags to simulate a hanging network request
    def hanging_fetch_flags(self):
        print("Simulating hanging network request...")
        time.sleep(2)  # Simulate a slow network request
        raise Exception("Network timeout simulation")
    
    with patch.object(FeatureFlagsHQSDK, '_fetch_flags', hanging_fetch_flags):
        start_time = time.time()
        
        # Create SDK instance (this will trigger the hanging _fetch_flags)
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=False  # This will trigger network calls
        )
        
        init_time = time.time() - start_time
        print(f"SDK initialization took {init_time:.2f} seconds")
        
        # Add a test flag to the SDK
        test_flag = FeatureFlagsHQFlag(
            name="test_flag", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )
        sdk.feature_flags["test_flag"] = test_flag
        
        # Test get() method - this should NOT hang
        get_start_time = time.time()
        result = sdk.get("user123", "test_flag", False)
        get_time = time.time() - get_start_time
        
        print(f"get() method took {get_time:.2f} seconds")
        print(f"get() result: {result}")
        
        # Verify that get() method completed quickly (within 1 second)
        assert get_time < 1.0, f"get() method took too long: {get_time:.2f} seconds"
        
        # Verify that the result is correct
        assert result == True, f"Expected True, got {result}"
        
        sdk.shutdown()
        
    print("[PASS] Test passed: get() method completed quickly even with hanging initialization")


def test_get_method_with_nonexistent_flag():
    """Test get() method with non-existent flag after hanging initialization"""
    print("\nTesting get() method with non-existent flag...")
    
    def hanging_fetch_flags(self):
        time.sleep(1)  # Simulate network delay
        return {}
    
    with patch.object(FeatureFlagsHQSDK, '_fetch_flags', hanging_fetch_flags):
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=False
        )
        
        start_time = time.time()
        result = sdk.get("user123", "nonexistent_flag", "default_value")
        elapsed_time = time.time() - start_time
        
        print(f"get() with non-existent flag took {elapsed_time:.2f} seconds")
        print(f"Result: {result}")
        
        assert elapsed_time < 1.0, f"get() took too long: {elapsed_time:.2f} seconds"
        assert result == "default_value", f"Expected 'default_value', got {result}"
        
        sdk.shutdown()
        
    print("[PASS] Test passed: get() method with non-existent flag completed quickly")


def test_multiple_consecutive_gets():
    """Test multiple consecutive get() calls after hanging initialization"""
    print("\nTesting multiple consecutive get() calls...")
    
    def hanging_fetch_flags(self):
        time.sleep(1)
        return {}
    
    with patch.object(FeatureFlagsHQSDK, '_fetch_flags', hanging_fetch_flags):
        sdk = FeatureFlagsHQSDK(
            client_id="test_client", 
            client_secret="test_secret",
            offline_mode=False
        )
        
        # Add test flag
        test_flag = FeatureFlagsHQFlag(
            name="multi_test_flag", type="string", value="test_value", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )
        sdk.feature_flags["multi_test_flag"] = test_flag
        
        # Test multiple consecutive calls
        total_start_time = time.time()
        results = []
        
        for i in range(5):
            start_time = time.time()
            result = sdk.get(f"user{i}", "multi_test_flag", "default")
            elapsed = time.time() - start_time
            results.append((result, elapsed))
            print(f"Call {i+1}: {result} (took {elapsed:.3f}s)")
        
        total_time = time.time() - total_start_time
        print(f"Total time for 5 calls: {total_time:.2f} seconds")
        
        # Each call should be fast
        for i, (result, elapsed) in enumerate(results):
            assert elapsed < 0.5, f"Call {i+1} took too long: {elapsed:.3f} seconds"
            assert result == "test_value", f"Call {i+1} returned wrong value: {result}"
        
        sdk.shutdown()
        
    print("[PASS] Test passed: Multiple consecutive get() calls completed quickly")


if __name__ == "__main__":
    print("Running fix verification tests...\n")
    
    test_get_method_with_hanging_initialization()
    test_get_method_with_nonexistent_flag() 
    test_multiple_consecutive_gets()
    
    print("\nAll tests passed! The fix successfully prevents get() method from hanging.")