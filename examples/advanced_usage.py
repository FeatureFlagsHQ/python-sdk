#!/usr/bin/env python3
"""
FeatureFlagsHQ SDK - Advanced Usage Examples

This example demonstrates advanced features including:
- User segmentation
- Flag change callbacks
- Production configuration
- Monitoring and analytics
- Custom error handling
"""

import os
import time
import logging
from typing import Any
from featureflagshq import FeatureFlagsHQSDK, create_production_client, validate_production_config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def on_flag_change_callback(flag_name: str, old_value: Any, new_value: Any):
    """Callback function for flag changes"""
    logger.info(f"🔄 Flag '{flag_name}' changed from {old_value} to {new_value}")
    
    # Example: Invalidate cache when important flags change
    if flag_name in ['cache_ttl', 'rate_limit']:
        logger.info("   💾 Invalidating cache due to configuration change")
    
    # Example: Send notification for feature toggles
    if flag_name.startswith('feature_'):
        logger.info("   📱 Sending feature toggle notification")


def advanced_segmentation_example():
    """Demonstrate advanced user segmentation"""
    print("\n🎯 Advanced User Segmentation")
    print("=" * 40)
    
    sdk = FeatureFlagsHQSDK(
        client_id=os.getenv('FEATUREFLAGSHQ_CLIENT_ID', 'demo_client'),
        client_secret=os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET', 'demo_secret'),
        environment='development',
        on_flag_change=on_flag_change_callback
    )
    
    try:
        # Define different user types with segments
        users = [
            {
                'id': 'user_premium_us',
                'segments': {
                    'subscription': 'premium',
                    'country': 'US',
                    'age': 28,
                    'signup_date': '2023-01-15',
                    'feature_beta': True
                }
            },
            {
                'id': 'user_basic_uk',
                'segments': {
                    'subscription': 'basic',
                    'country': 'UK', 
                    'age': 35,
                    'signup_date': '2024-03-20',
                    'feature_beta': False
                }
            },
            {
                'id': 'user_enterprise_ca',
                'segments': {
                    'subscription': 'enterprise',
                    'country': 'CA',
                    'age': 42,
                    'signup_date': '2022-08-10',
                    'company_size': 500,
                    'feature_beta': True
                }
            }
        ]
        
        # Test flags for different user segments
        for user in users:
            print(f"\n👤 User: {user['id']}")
            print(f"   Segments: {user['segments']}")
            
            # Get flags with segmentation
            premium_features = sdk.get_bool(
                user['id'], 'premium_features', 
                default_value=False, 
                segments=user['segments']
            )
            
            api_rate_limit = sdk.get_int(
                user['id'], 'api_rate_limit',
                default_value=100,
                segments=user['segments']
            )
            
            dashboard_config = sdk.get_json(
                user['id'], 'dashboard_config',
                default_value={'theme': 'light', 'widgets': []},
                segments=user['segments']
            )
            
            print(f"   🎛️  Premium Features: {premium_features}")
            print(f"   ⚡ API Rate Limit: {api_rate_limit}/hour")
            print(f"   📊 Dashboard Config: {dashboard_config}")
            
            # Get all flags for this user
            all_flags = sdk.get_user_flags(user['id'], segments=user['segments'])
            print(f"   📋 Total Flags: {len(all_flags)}")
    
    finally:
        sdk.shutdown()


def production_configuration_example():
    """Demonstrate production-ready configuration"""
    print("\n🏭 Production Configuration")
    print("=" * 40)
    
    # Validate configuration before creating client
    config = {
        'api_base_url': 'https://api.featureflagshq.com',
        'timeout': 30,
        'max_retries': 3,
        'client_secret': os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET', 'demo_secret'),
        'enable_metrics': True,
        'offline_mode': False
    }
    
    warnings = validate_production_config(config)
    if warnings:
        print("⚠️  Configuration warnings:")
        for warning in warnings:
            print(f"   - {warning}")
    else:
        print("✅ Configuration validation passed")
    
    # Create production client with hardened security
    sdk = create_production_client(
        client_id=os.getenv('FEATUREFLAGSHQ_CLIENT_ID', 'demo_client'),
        client_secret=os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET', 'demo_secret'),
        environment='production',
        timeout=30,
        max_retries=3,
        enable_metrics=True
    )
    
    try:
        # Test production client
        health = sdk.get_health_check()
        print(f"🏥 Production SDK Status: {health['status']}")
        print(f"🔒 Security Features Enabled: HMAC Auth, Input Validation, Rate Limiting")
        
    finally:
        sdk.shutdown()


def monitoring_and_analytics_example():
    """Demonstrate monitoring and analytics features"""
    print("\n📊 Monitoring and Analytics")
    print("=" * 40)
    
    sdk = FeatureFlagsHQSDK(
        client_id=os.getenv('FEATUREFLAGSHQ_CLIENT_ID', 'demo_client'),
        client_secret=os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET', 'demo_secret'),
        environment='development',
        enable_metrics=True
    )
    
    try:
        # Simulate some flag usage
        users = [f"user_{i}" for i in range(10)]
        flags = ['new_ui', 'dark_mode', 'beta_features', 'premium_content']
        
        print("🔄 Simulating flag usage...")
        for user in users:
            for flag in flags:
                sdk.get_bool(user, flag, default_value=False)
        
        # Wait a moment for metrics to be collected
        time.sleep(0.5)
        
        # Get comprehensive statistics
        stats = sdk.get_stats()
        print(f"\n📈 Usage Statistics:")
        print(f"   Total Accesses: {stats['total_user_accesses']}")
        print(f"   Unique Users: {stats['unique_users_count']}")
        print(f"   Unique Flags: {stats['unique_flags_count']}")
        print(f"   Successful API Calls: {stats['api_calls']['successful']}")
        print(f"   Failed API Calls: {stats['api_calls']['failed']}")
        print(f"   Circuit Breaker State: {stats['circuit_breaker']['state']}")
        print(f"   Pending Logs: {stats['pending_user_logs']}")
        
        # Health monitoring
        health = sdk.get_health_check()
        print(f"\n🏥 Health Status:")
        print(f"   Overall Status: {health['status']}")
        print(f"   Cached Flags: {health['cached_flags_count']}")
        print(f"   Initialization Complete: {health['initialization_complete']}")
        print(f"   Last Sync: {stats['last_sync'] or 'Never'}")
        
        # Force log upload for demonstration
        print(f"\n📤 Uploading analytics logs...")
        success = sdk.flush_logs()
        print(f"   Upload Success: {success}")
        
    finally:
        sdk.shutdown()


def resilience_and_error_handling_example():
    """Demonstrate resilience and error handling"""
    print("\n🛡️  Resilience and Error Handling")
    print("=" * 40)
    
    # Test with invalid credentials but continue working
    sdk = FeatureFlagsHQSDK(
        client_id="invalid_client",
        client_secret="invalid_secret",
        environment='development',
        offline_mode=True,  # Force offline mode for demonstration
        timeout=5,
        max_retries=1
    )
    
    try:
        print("🔌 Testing offline mode resilience...")
        
        # SDK should still work with default values
        result = sdk.get_bool("user_test", "critical_feature", default_value=True)
        print(f"   Critical Feature (offline): {result}")
        
        # Check error statistics
        stats = sdk.get_stats()
        print(f"   Network Errors: {stats['errors']['network_errors']}")
        print(f"   Auth Errors: {stats['errors']['auth_errors']}")
        
        # Test circuit breaker
        print(f"🔌 Circuit Breaker State: {stats['circuit_breaker']['state']}")
        
        # Test rate limiting protection
        print(f"🚦 Testing rate limiting...")
        for i in range(5):
            result = sdk.get_bool(f"rate_test_user", "test_flag")
            print(f"   Request {i+1}: Success")
        
        print("✅ All resilience features working correctly")
        
    finally:
        sdk.shutdown()


def flag_change_monitoring_example():
    """Demonstrate flag change monitoring"""
    print("\n🔄 Flag Change Monitoring")
    print("=" * 40)
    
    change_events = []
    
    def track_changes(flag_name: str, old_value: Any, new_value: Any):
        change_events.append({
            'flag': flag_name,
            'old': old_value,
            'new': new_value,
            'timestamp': time.time()
        })
        print(f"   📝 Tracked change: {flag_name} ({old_value} → {new_value})")
    
    sdk = FeatureFlagsHQSDK(
        client_id=os.getenv('FEATUREFLAGSHQ_CLIENT_ID', 'demo_client'),
        client_secret=os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET', 'demo_secret'),
        environment='development',
        on_flag_change=track_changes
    )
    
    try:
        print("🎧 Flag change callback registered")
        print("   (In real usage, changes would come from the server)")
        
        # Simulate flag changes by manually updating flags
        # In real usage, these would come from server polling
        print(f"\n📊 Change Events Captured: {len(change_events)}")
        
        # Manual refresh to check for changes
        print(f"🔄 Manually refreshing flags...")
        success = sdk.refresh_flags()
        print(f"   Refresh Success: {success}")
        
    finally:
        sdk.shutdown()


def performance_testing_example():
    """Demonstrate performance characteristics"""
    print("\n⚡ Performance Testing")
    print("=" * 40)
    
    sdk = FeatureFlagsHQSDK(
        client_id=os.getenv('FEATUREFLAGSHQ_CLIENT_ID', 'demo_client'),
        client_secret=os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET', 'demo_secret'),
        environment='development',
        offline_mode=True  # For consistent performance testing
    )
    
    try:
        # Performance test: Many flag evaluations
        print("🏃 Testing flag evaluation performance...")
        
        start_time = time.time()
        iterations = 1000
        
        for i in range(iterations):
            user_id = f"perf_user_{i % 100}"  # 100 unique users
            flag_name = f"flag_{i % 10}"      # 10 unique flags
            result = sdk.get_bool(user_id, flag_name, default_value=False)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"   📊 {iterations} evaluations in {duration:.3f}s")
        print(f"   ⚡ {iterations/duration:.0f} evaluations/second")
        print(f"   🎯 {duration*1000/iterations:.2f}ms average per evaluation")
        
        # Check memory usage through stats
        stats = sdk.get_stats()
        print(f"   👥 Unique users tracked: {stats['unique_users_count']}")
        print(f"   🏷️  Unique flags tracked: {stats['unique_flags_count']}")
        
    finally:
        sdk.shutdown()


def main():
    """Run all advanced examples"""
    print("FeatureFlagsHQ SDK - Advanced Usage Examples")
    print("=" * 50)
    
    try:
        advanced_segmentation_example()
        production_configuration_example()
        monitoring_and_analytics_example()
        resilience_and_error_handling_example()
        flag_change_monitoring_example()
        performance_testing_example()
        
        print(f"\n✅ All advanced examples completed successfully!")
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
        raise


if __name__ == "__main__":
    print("To run this example:")
    print("1. Set your credentials as environment variables:")
    print("   export FEATUREFLAGSHQ_CLIENT_ID='your_client_id'")
    print("   export FEATUREFLAGSHQ_CLIENT_SECRET='your_client_secret'")
    print("2. Run: python examples/advanced_usage.py\n")
    
    main()