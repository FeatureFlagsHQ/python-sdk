#!/usr/bin/env python3
"""
FeatureFlagsHQ SDK - Basic Usage Examples

This example demonstrates basic usage of the FeatureFlagsHQ SDK
for feature flag management.
"""

import os
from featureflagshq import FeatureFlagsHQSDK

def main():
    print("FeatureFlagsHQ SDK - Basic Usage Examples")
    print("=" * 50)
    
    # Initialize SDK with credentials
    # You can set these as environment variables or pass them directly
    sdk = FeatureFlagsHQSDK(
        client_id=os.getenv('FEATUREFLAGSHQ_CLIENT_ID', 'your_client_id'),
        client_secret=os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET', 'your_client_secret'),
        environment=os.getenv('FEATUREFLAGSHQ_ENVIRONMENT', 'development')
    )
    
    try:
        print("✅ SDK initialized successfully")
        
        # Example user
        user_id = "user_123"
        
        print(f"\n🧪 Testing flags for user: {user_id}")
        print("-" * 30)
        
        # Boolean flag example
        show_new_feature = sdk.get_bool(
            user_id=user_id,
            flag_name="new_dashboard",
            default_value=False
        )
        print(f"🎛️  New Dashboard Enabled: {show_new_feature}")
        
        # String flag example
        theme_color = sdk.get_string(
            user_id=user_id,
            flag_name="theme_color",
            default_value="blue"
        )
        print(f"🎨 Theme Color: {theme_color}")
        
        # Integer flag example
        max_items = sdk.get_int(
            user_id=user_id,
            flag_name="max_items_per_page",
            default_value=10
        )
        print(f"📄 Max Items Per Page: {max_items}")
        
        # Float flag example
        discount_rate = sdk.get_float(
            user_id=user_id,
            flag_name="discount_rate",
            default_value=0.0
        )
        print(f"💰 Discount Rate: {discount_rate}%")
        
        # JSON flag example
        feature_config = sdk.get_json(
            user_id=user_id,
            flag_name="feature_config",
            default_value={"enabled": False, "timeout": 30}
        )
        print(f"⚙️  Feature Config: {feature_config}")
        
        # Check if a flag is enabled (convenience method)
        is_beta_user = sdk.is_flag_enabled_for_user(
            user_id=user_id,
            flag_name="beta_features"
        )
        print(f"🧪 Beta Features Enabled: {is_beta_user}")
        
        # Get multiple flags at once
        print(f"\n📊 All flags for user {user_id}:")
        print("-" * 30)
        all_flags = sdk.get_user_flags(user_id)
        for flag_name, flag_value in all_flags.items():
            print(f"   {flag_name}: {flag_value}")
        
        # SDK health check
        print(f"\n🏥 SDK Health Check:")
        print("-" * 30)
        health = sdk.get_health_check()
        print(f"   Status: {health['status']}")
        print(f"   Cached Flags: {health['cached_flags_count']}")
        print(f"   Environment: {health['environment']}")
        
        # SDK usage statistics
        print(f"\n📈 SDK Statistics:")
        print("-" * 30)
        stats = sdk.get_stats()
        print(f"   Total Access Calls: {stats['total_user_accesses']}")
        print(f"   Unique Users: {stats['unique_users_count']}")
        print(f"   API Calls: {stats['api_calls']['total']} (Success: {stats['api_calls']['successful']})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        # Always clean up resources
        print(f"\n🧹 Shutting down SDK...")
        sdk.shutdown()
        print("✅ SDK shutdown complete")


def example_with_context_manager():
    """Example using context manager for automatic cleanup"""
    print(f"\n🔄 Context Manager Example:")
    print("-" * 30)
    
    # Using context manager - automatic cleanup
    with FeatureFlagsHQSDK(
        client_id=os.getenv('FEATUREFLAGSHQ_CLIENT_ID', 'your_client_id'),
        client_secret=os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET', 'your_client_secret'),
        environment='development'
    ) as sdk:
        
        result = sdk.get_bool("user_456", "auto_save", default_value=True)
        print(f"   Auto Save Enabled: {result}")
        
        # SDK automatically shuts down when exiting the context
    
    print("   ✅ SDK automatically cleaned up")


def example_error_handling():
    """Example demonstrating error handling"""
    print(f"\n🛡️  Error Handling Example:")
    print("-" * 30)
    
    try:
        # Example with invalid credentials
        sdk = FeatureFlagsHQSDK(
            client_id="invalid_id",
            client_secret="invalid_secret",
            offline_mode=True  # Use offline mode to prevent actual API calls
        )
        
        # SDK will still work but return default values
        result = sdk.get_bool("user_789", "test_flag", default_value=False)
        print(f"   Flag value (offline): {result}")
        
        # Check SDK health to see issues
        health = sdk.get_health_check()
        print(f"   SDK Status: {health['status']}")
        
        sdk.shutdown()
        
    except ValueError as e:
        print(f"   ⚠️  Configuration Error: {e}")
    except Exception as e:
        print(f"   ❌ Unexpected Error: {e}")


if __name__ == "__main__":
    print("To run this example:")
    print("1. Set your credentials as environment variables:")
    print("   export FEATUREFLAGSHQ_CLIENT_ID='your_client_id'")
    print("   export FEATUREFLAGSHQ_CLIENT_SECRET='your_client_secret'")
    print("2. Run: python examples/basic_usage.py\n")
    
    main()
    example_with_context_manager()
    example_error_handling()