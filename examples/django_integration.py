"""
FeatureFlagsHQ Django Integration Example

This example shows how to integrate FeatureFlagsHQ with Django applications.
"""

import os
from django.conf import settings
from django.apps import AppConfig
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_page
import featureflagshq


# App Configuration
class MyAppConfig(AppConfig):
    name = 'myapp'
    
    def ready(self):
        """Initialize FeatureFlagsHQ client when Django starts"""
        try:
            self.feature_flags = featureflagshq.create_client(
                client_id=settings.FEATUREFLAGSHQ_CLIENT_ID,
                client_secret=settings.FEATUREFLAGSHQ_CLIENT_SECRET,
                environment=getattr(settings, 'FEATUREFLAGSHQ_ENVIRONMENT', 'production'),
                debug=settings.DEBUG
            )
            print("✅ FeatureFlagsHQ initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize FeatureFlagsHQ: {e}")
            # Fallback to offline mode
            self.feature_flags = featureflagshq.create_client(
                client_id="fallback",
                client_secret="fallback",
                offline_mode=True
            )


# Middleware for feature flags
class FeatureFlagsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Add feature flags client to request
        from django.apps import apps
        app_config = apps.get_app_config('myapp')
        request.feature_flags = app_config.feature_flags
        
        response = self.get_response(request)
        return response


# Template context processor
def feature_flags_processor(request):
    """Add common feature flags to template context"""
    if not hasattr(request, 'feature_flags') or not request.user.is_authenticated:
        return {}
    
    user_id = str(request.user.id)
    user_segments = {
        'is_staff': request.user.is_staff,
        'is_premium': getattr(request.user, 'is_premium', False),
        'device': request.META.get('HTTP_USER_AGENT', '').lower()
    }
    
    return {
        'feature_flags': {
            'new_dashboard': request.feature_flags.get_bool(user_id, 'new_dashboard', segments=user_segments),
            'beta_features': request.feature_flags.get_bool(user_id, 'beta_features', segments=user_segments),
            'advanced_search': request.feature_flags.get_bool(user_id, 'advanced_search', segments=user_segments),
        }
    }


# Views
def dashboard_view(request):
    """Dashboard view with feature flag integration"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    user_id = str(request.user.id)
    user_segments = {
        'subscription': getattr(request.user, 'subscription_type', 'free'),
        'join_date': request.user.date_joined.strftime('%Y-%m-%d'),
        'is_staff': request.user.is_staff
    }
    
    # Check feature flags
    new_dashboard = request.feature_flags.get_bool(user_id, 'new_dashboard', segments=user_segments)
    max_projects = request.feature_flags.get_int(user_id, 'max_projects', default_value=5, segments=user_segments)
    
    template = 'dashboard_new.html' if new_dashboard else 'dashboard_old.html'
    
    context = {
        'max_projects': max_projects,
        'new_dashboard': new_dashboard,
        'user_segments': user_segments
    }
    
    return render(request, template, context)


@cache_page(60 * 5)  # Cache for 5 minutes
def api_config_view(request):
    """API endpoint to get feature flags configuration"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    user_id = str(request.user.id)
    user_segments = {
        'subscription': getattr(request.user, 'subscription_type', 'free'),
        'region': request.META.get('HTTP_CF_IPCOUNTRY', 'US'),
        'device': 'mobile' if 'mobile' in request.META.get('HTTP_USER_AGENT', '').lower() else 'desktop'
    }
    
    # Get multiple feature flags at once
    flags = request.feature_flags.get_user_flags(
        user_id,
        segments=user_segments,
        flag_keys=['api_v2', 'rate_limit_increase', 'new_endpoints']
    )
    
    return JsonResponse({
        'flags': flags,
        'user_id': user_id,
        'segments': user_segments
    })


# Settings configuration example
"""
# settings.py

# FeatureFlagsHQ Configuration
FEATUREFLAGSHQ_CLIENT_ID = os.getenv('FEATUREFLAGSHQ_CLIENT_ID')
FEATUREFLAGSHQ_CLIENT_SECRET = os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET') 
FEATUREFLAGSHQ_ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')

# Add to installed apps
INSTALLED_APPS = [
    # ... other apps
    'myapp.apps.MyAppConfig',  # Use the custom app config
]

# Add middleware
MIDDLEWARE = [
    # ... other middleware
    'myapp.middleware.FeatureFlagsMiddleware',
]

# Add template context processor
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'OPTIONS': {
            'context_processors': [
                # ... other processors
                'myapp.context_processors.feature_flags_processor',
            ],
        },
    },
]
"""