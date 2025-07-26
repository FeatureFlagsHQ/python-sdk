"""
FeatureFlagsHQ Flask Integration Example

This example demonstrates how to integrate FeatureFlagsHQ with Flask applications.
"""

import os
import functools
from flask import Flask, request, jsonify, render_template, session, g
import featureflagshq


def create_app():
    """Application factory with FeatureFlagsHQ integration"""
    app = Flask(__name__)
    app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    # FeatureFlagsHQ configuration
    app.config.update({
        'FEATUREFLAGSHQ_CLIENT_ID': os.getenv('FEATUREFLAGSHQ_CLIENT_ID'),
        'FEATUREFLAGSHQ_CLIENT_SECRET': os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET'),
        'FEATUREFLAGSHQ_ENVIRONMENT': os.getenv('ENVIRONMENT', 'production'),
    })
    
    # Initialize FeatureFlagsHQ
    @app.before_first_request
    def init_feature_flags():
        """Initialize feature flags client on first request"""
        try:
            app.feature_flags = featureflagshq.create_client(
                client_id=app.config['FEATUREFLAGSHQ_CLIENT_ID'],
                client_secret=app.config['FEATUREFLAGSHQ_CLIENT_SECRET'],
                environment=app.config['FEATUREFLAGSHQ_ENVIRONMENT'],
                debug=app.debug
            )
            app.logger.info("✅ FeatureFlagsHQ initialized successfully")
        except Exception as e:
            app.logger.error(f"❌ Failed to initialize FeatureFlagsHQ: {e}")
            # Fallback to offline mode
            app.feature_flags = featureflagshq.create_client(
                client_id="fallback",
                client_secret="fallback", 
                offline_mode=True
            )
    
    # Make feature flags available in templates
    @app.context_processor
    def inject_feature_flags():
        """Inject feature flags into template context"""
        user_id = session.get('user_id')
        if not user_id:
            return {}
        
        user_segments = {
            'subscription': session.get('subscription', 'free'),
            'region': request.headers.get('CF-IPCountry', 'US'),
            'user_agent': request.headers.get('User-Agent', '')
        }
        
        return {
            'ff': {
                'new_ui': app.feature_flags.get_bool(user_id, 'new_ui', segments=user_segments),
                'beta_features': app.feature_flags.get_bool(user_id, 'beta_features', segments=user_segments),
                'premium_features': app.feature_flags.get_bool(user_id, 'premium_features', segments=user_segments),
            }
        }
    
    # Feature flag decorator
    def require_feature_flag(flag_name, default_value=False):
        """Decorator to require a feature flag to access a route"""
        def decorator(f):
            @functools.wraps(f)
            def decorated_function(*args, **kwargs):
                user_id = session.get('user_id')
                if not user_id:
                    return jsonify({'error': 'Authentication required'}), 401
                
                user_segments = get_user_segments()
                flag_enabled = app.feature_flags.get_bool(
                    user_id, flag_name, default_value=default_value, segments=user_segments
                )
                
                if not flag_enabled:
                    return jsonify({'error': 'Feature not available'}), 403
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    def get_user_segments():
        """Helper function to build user segments"""
        return {
            'subscription': session.get('subscription', 'free'),
            'region': request.headers.get('CF-IPCountry', 'US'),
            'device': 'mobile' if 'mobile' in request.headers.get('User-Agent', '').lower() else 'desktop',
            'is_premium': session.get('subscription') == 'premium'
        }
    
    # Routes
    @app.route('/')
    def index():
        """Home page with feature flag integration"""
        user_id = session.get('user_id', 'anonymous')
        user_segments = get_user_segments() if session.get('user_id') else {}
        
        # Get feature flags
        welcome_message = app.feature_flags.get_string(
            user_id, 'welcome_message', default_value='Welcome!', segments=user_segments
        )
        
        show_