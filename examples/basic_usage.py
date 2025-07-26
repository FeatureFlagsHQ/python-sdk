#!/usr/bin/env python3
"""
FeatureFlagsHQ Python SDK - Basic Usage Example

This example demonstrates the core functionality of the FeatureFlagsHQ SDK.
"""

import os
import time
import featureflagshq

def main():
    """Basic usage example"""
    
    # Get credentials from environment variables
    client_id = os.getenv('FEATUREFLAGSHQ_CLIENT_ID')
    client_secret = os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("❌ Please set FEATUREFLAGSHQ_CLIENT_ID and FEATUREFLAGSHQ_CLIENT_SECRET environment variables")
        print("   export FEATUREFLAGSHQ_CLIENT_ID='your-client-id'")
        print("   export FEATUREFLAGSHQ_CLIENT_SECRET='your-client-secret'")
        return
    
    # Create client with context manager (recommended)
    with featureflagshq.create_client(client_id, client_secret) as client:
        print("🚀 FeatureFlagsHQ SDK initialized successfully!")
        
        # Example user
        user_id = "user_123"
        
        # 1. Boolean flag
        print("\n📝 Testing Boolean Flags:")
        new_ui_enabled = client.get_bool(user_id, "new_ui", default_value=False)
        print(f"   New UI enabled for {user_id}: {new_ui_enabled}")
        
        # 2. String flag
        print("\n📝 Testing String Flags:")
        welcome_message = client.get_string(user_id, "welcome_message", default_value="Welcome!")
        print(f"   Welcome message: '{welcome_message}'")
        
        # 3. Integer flag
        print("\n📝 Testing Integer Flags:")
        max_items = client.get_int(user_id, "max_items_per_page", default_value=10)
        print(f"   Max items per page: {max_items}")
        
        # 4. Float flag
        print("\n📝 Testing Float Flags:")
        discount_rate = client.get_float(user_id, "discount_rate", default_value=0.0)
        print(f"   Discount rate: {discount_rate:.2%}")
        
        # 5. JSON flag
        print("\n📝 Testing JSON Flags:")
        ui_config = client.get_json(user_id, "ui_config", default_value={"theme": "light"})
        print(f"   UI config: {ui_config}")
        
        # 6. Using segments for targeting
        print("\n🎯 Testing Targeted Flags with Segments:")
        user_segments = {
            "subscription": "premium",
            "region": "us-west",
            "device": "mobile"
        }
        
        premium_feature = client.get_bool(
            user_id, 
            "premium_feature", 
            default_value=False,
            segments=user_segments
        )
        print(f"   Premium feature enabled: {premium_feature}")
        
        # 7. Batch flag evaluation
        print("\n📦 Testing Batch Flag Evaluation:")
        flag_keys = ["new_ui", "premium_feature", "max_items_per_page"]
        user_flags = client.get_user_flags(user_id, segments=user_segments, flag_keys=flag_keys)
        
        print("   User's flags:")
        for flag_name, flag_value in user_flags.items():
            print(f"     {flag_name}: {flag_value}")
        
        # 8. SDK statistics
        print("\n📊 SDK Statistics:")
        stats = client.get_stats()
        print(f"   Total evaluations: {stats['total_user_accesses']}")
        print(f"   Unique users: {stats.get('unique_users_count', 0)}")
        print(f"   Average evaluation time: {stats['evaluation_times']['avg_ms']:.2f}ms")
        
        # 9. Health check
        print("\n🏥 Health Check:")
        health = client.get_health_check()
        print(f"   Status: {health['status']}")
        print(f"   Cached flags: {health['cached_flags_count']}")
        print(f"   Last sync: {health['last_sync']}")
        
        print("\n✅ Example completed successfully!")

if __name__ == "__main__":
    main()