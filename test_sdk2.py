#!/usr/bin/env python3
"""
Test script to verify the simplified SDK2 implementation
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from featureflagshq.sdk2 import FeatureFlagSDK
import time
from unittest.mock import patch, Mock

def test_sdk2_initialization():
    """Test SDK2 initialization with environment variables and parameters"""
    print("Testing SDK2 initialization...")
    
    # Test with direct parameters
    try:
        sdk = FeatureFlagSDK(
            client_id="test_client_id",
            client_secret="test_client_secret",
            environment="staging"
        )
        print("✓ Direct parameter initialization works")
        
        # Check that environment is set correctly
        assert sdk.environment == "staging"
        print("✓ Environment parameter works")
        
        sdk.shutdown()
    except Exception as e:
        print(f"✗ Direct initialization failed: {e}")
        return False
    
    # Test with environment variables
    try:
        with patch.dict(os.environ, {
            'FEATUREFLAGSHQ_CLIENT_ID': 'env_client_id',
            'FEATUREFLAGSHQ_CLIENT_SECRET': 'env_client_secret',
            'FEATUREFLAGSHQ_ENVIRONMENT': 'development'
        }):
            sdk = FeatureFlagSDK()
            print("✓ Environment variable initialization works")
            
            # Check environment variables are used
            assert sdk.client_id == "env_client_id"
            assert sdk.client_secret == "env_client_secret"
            assert sdk.environment == "development"
            print("✓ Environment variables are read correctly")
            
            sdk.shutdown()
    except Exception as e:
        print(f"✗ Environment variable initialization failed: {e}")
        return False
    
    return True

def test_sdk2_headers():
    """Test that headers match the expected format"""
    print("\nTesting SDK2 headers...")
    
    sdk = FeatureFlagSDK(
        client_id="test_client",
        client_secret="test_secret",
        environment="test_env"
    )
    
    try:
        headers = sdk._get_headers("test_payload")
        
        # Check required headers are present
        required_headers = [
            'Content-Type',
            'X-SDK-Provider', 
            'X-Client-ID',
            'X-Timestamp',
            'X-Signature',
            'X-Session-ID',
            'X-SDK-Version',
            'X-Environment',
            'User-Agent'
        ]
        
        for header in required_headers:
            if header not in headers:
                print(f"✗ Missing required header: {header}")
                return False
        
        print("✓ All required headers present")
        
        # Check header values
        assert headers['X-Client-ID'] == "test_client"
        assert headers['X-Environment'] == "test_env"
        assert headers['X-SDK-Provider'] == "FeatureFlagsHQ"
        assert headers['Content-Type'] == "application/json"
        
        print("✓ Header values are correct")
        
        # Check signature is generated
        assert headers['X-Signature']
        assert headers['X-Timestamp']
        print("✓ Signature and timestamp generated")
        
        sdk.shutdown()
        return True
        
    except Exception as e:
        print(f"✗ Header test failed: {e}")
        sdk.shutdown()
        return False

def test_sdk2_validation():
    """Test input validation"""
    print("\nTesting SDK2 input validation...")
    
    # Test invalid credentials
    try:
        sdk = FeatureFlagSDK(client_id="", client_secret="")
        print("✗ Should have failed with empty credentials")
        return False
    except ValueError:
        print("✓ Empty credentials rejected")
    
    # Test SQL injection prevention
    try:
        sdk = FeatureFlagSDK(
            client_id="test_client",
            client_secret="test_secret"
        )
        
        # Test dangerous user ID
        try:
            sdk._validate_user_id("user'; DROP TABLE users; --")
            print("✗ Should have rejected SQL injection attempt")
            return False
        except ValueError:
            print("✓ SQL injection in user_id rejected")
        
        # Test dangerous flag name
        try:
            sdk._validate_flag_name("flag UNION SELECT * FROM secrets")
            print("✗ Should have rejected SQL injection attempt")
            return False
        except ValueError:
            print("✓ SQL injection in flag_name rejected")
        
        # Test length limits
        try:
            sdk._validate_user_id("a" * 300)  # Over 255 characters
            print("✗ Should have rejected long user_id")
            return False
        except ValueError:
            print("✓ Long user_id rejected")
        
        sdk.shutdown()
        return True
        
    except Exception as e:
        print(f"✗ Validation test failed: {e}")
        return False

def test_sdk2_offline_functionality():
    """Test offline functionality with mocked data"""
    print("\nTesting SDK2 offline functionality...")
    
    # Mock the _fetch_flags method to return test data
    def mock_fetch_flags(self):
        return {
            "test_bool_flag": {
                "name": "test_bool_flag",
                "type": "bool",
                "value": "true",
                "is_active": True
            },
            "test_string_flag": {
                "name": "test_string_flag", 
                "type": "string",
                "value": "hello_world",
                "is_active": True
            },
            "test_int_flag": {
                "name": "test_int_flag",
                "type": "int", 
                "value": "42",
                "is_active": True
            }
        }
    
    with patch.object(FeatureFlagSDK, '_fetch_flags', mock_fetch_flags):
        sdk = FeatureFlagSDK(
            client_id="test_client",
            client_secret="test_secret"
        )
        
        try:
            # Test flag retrieval
            bool_result = sdk.get_bool("user123", "test_bool_flag")
            assert bool_result == True
            print("✓ Boolean flag retrieval works")
            
            string_result = sdk.get_string("user123", "test_string_flag")
            assert string_result == "hello_world"
            print("✓ String flag retrieval works")
            
            int_result = sdk.get_int("user123", "test_int_flag")
            assert int_result == 42
            print("✓ Integer flag retrieval works")
            
            # Test non-existent flag
            default_result = sdk.get("user123", "nonexistent_flag", "default")
            assert default_result == "default"
            print("✓ Default value for non-existent flag works")
            
            sdk.shutdown()
            return True
            
        except Exception as e:
            print(f"✗ Offline functionality test failed: {e}")
            sdk.shutdown()
            return False

def main():
    """Run all tests"""
    print("Running SDK2 verification tests...\n")
    
    tests = [
        test_sdk2_initialization,
        test_sdk2_headers,
        test_sdk2_validation,
        test_sdk2_offline_functionality
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()  # Add spacing between tests
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! SDK2 is working correctly.")
        return True
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)