#!/usr/bin/env python3
"""
FeatureFlagsHQ SDK - Django Integration Example

This example shows how to integrate FeatureFlagsHQ SDK with Django applications,
including middleware, template tags, and management commands.
"""

# =============================================================================
# Django Settings Configuration
# =============================================================================

# Add to your Django settings.py:
DJANGO_SETTINGS_EXAMPLE = """
# settings.py

# FeatureFlagsHQ Configuration
FEATUREFLAGSHQ_CLIENT_ID = os.getenv('FEATUREFLAGSHQ_CLIENT_ID')
FEATUREFLAGSHQ_CLIENT_SECRET = os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET')
FEATUREFLAGSHQ_ENVIRONMENT = os.getenv('FEATUREFLAGSHQ_ENVIRONMENT', 'production')
FEATUREFLAGSHQ_API_BASE_URL = 'https://api.featureflagshq.com'
FEATUREFLAGSHQ_TIMEOUT = 30
FEATUREFLAGSHQ_ENABLE_METRICS = True

# Optional: Configure SDK per environment
if DEBUG:
    FEATUREFLAGSHQ_ENVIRONMENT = 'development'
    FEATUREFLAGSHQ_ENABLE_METRICS = False  # Disable in development
"""

# =============================================================================
# SDK Service Module
# =============================================================================

# Create: myapp/services/feature_flags.py
FEATURE_FLAGS_SERVICE = """
# myapp/services/feature_flags.py

from django.conf import settings
from featureflagshq import FeatureFlagsHQSDK, create_production_client
import logging

logger = logging.getLogger(__name__)

class FeatureFlagService:
    '''Singleton service for managing feature flags in Django'''
    
    _instance = None
    _sdk = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._sdk is None:
            self._initialize_sdk()
    
    def _initialize_sdk(self):
        '''Initialize the FeatureFlagsHQ SDK'''
        try:
            if hasattr(settings, 'FEATUREFLAGSHQ_CLIENT_ID'):
                self._sdk = create_production_client(
                    client_id=settings.FEATUREFLAGSHQ_CLIENT_ID,
                    client_secret=settings.FEATUREFLAGSHQ_CLIENT_SECRET,
                    environment=getattr(settings, 'FEATUREFLAGSHQ_ENVIRONMENT', 'production'),
                    api_base_url=getattr(settings, 'FEATUREFLAGSHQ_API_BASE_URL', 'https://api.featureflagshq.com'),
                    timeout=getattr(settings, 'FEATUREFLAGSHQ_TIMEOUT', 30),
                    enable_metrics=getattr(settings, 'FEATUREFLAGSHQ_ENABLE_METRICS', True)
                )
                logger.info("FeatureFlagsHQ SDK initialized successfully")
            else:
                logger.warning("FeatureFlagsHQ credentials not configured")
                self._sdk = None
        except Exception as e:
            logger.error(f"Failed to initialize FeatureFlagsHQ SDK: {e}")
            self._sdk = None
    
    def get_user_context(self, request):
        '''Extract user context for feature flag evaluation'''
        if not request.user.is_authenticated:
            return None
        
        # Build user segments based on your user model
        segments = {
            'user_id': str(request.user.id),
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser,
        }
        
        # Add custom attributes if available
        if hasattr(request.user, 'subscription_type'):
            segments['subscription'] = request.user.subscription_type
        
        if hasattr(request.user, 'country'):
            segments['country'] = request.user.country
        
        # Add request-based context
        segments['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
        segments['ip_country'] = self._get_country_from_ip(request)
        
        return segments
    
    def _get_country_from_ip(self, request):
        '''Get country from IP address (implement based on your geo-IP service)'''
        # Placeholder - implement with your geo-IP service
        return 'US'
    
    def is_enabled(self, user_id, flag_name, default=False, segments=None):
        '''Check if a feature flag is enabled for a user'''
        if not self._sdk:
            return default
        
        try:
            return self._sdk.get_bool(user_id, flag_name, default, segments)
        except Exception as e:
            logger.error(f"Error checking flag {flag_name}: {e}")
            return default
    
    def get_flag_value(self, user_id, flag_name, default=None, segments=None):
        '''Get feature flag value for a user'''
        if not self._sdk:
            return default
        
        try:
            return self._sdk.get(user_id, flag_name, default, segments)
        except Exception as e:
            logger.error(f"Error getting flag {flag_name}: {e}")
            return default
    
    def get_user_flags(self, user_id, segments=None, flag_keys=None):
        '''Get all feature flags for a user'''
        if not self._sdk:
            return {}
        
        try:
            return self._sdk.get_user_flags(user_id, segments, flag_keys)
        except Exception as e:
            logger.error(f"Error getting user flags: {e}")
            return {}
    
    def get_health_status(self):
        '''Get SDK health status'''
        if not self._sdk:
            return {'status': 'not_configured'}
        
        return self._sdk.get_health_check()
    
    def shutdown(self):
        '''Shutdown SDK (call this in Django shutdown)'''
        if self._sdk:
            self._sdk.shutdown()
            self._sdk = None

# Global instance
feature_flags = FeatureFlagService()
"""

# =============================================================================
# Django Middleware
# =============================================================================

MIDDLEWARE_EXAMPLE = """
# myapp/middleware/feature_flags.py

from django.utils.deprecation import MiddlewareMixin
from myapp.services.feature_flags import feature_flags

class FeatureFlagMiddleware(MiddlewareMixin):
    '''Middleware to add feature flags to request context'''
    
    def process_request(self, request):
        '''Add feature flag context to request'''
        request.feature_flags = feature_flags
        
        # Add user context for authenticated users
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.user_segments = feature_flags.get_user_context(request)
            request.user_id = str(request.user.id)
        else:
            request.user_segments = {}
            request.user_id = f"anonymous_{request.session.session_key or 'unknown'}"
        
        return None
    
    def process_response(self, request, response):
        '''Clean up any resources if needed'''
        return response

# Add to settings.py MIDDLEWARE:
# MIDDLEWARE = [
#     ...
#     'myapp.middleware.feature_flags.FeatureFlagMiddleware',
#     ...
# ]
"""

# =============================================================================
# Template Context Processor
# =============================================================================

CONTEXT_PROCESSOR_EXAMPLE = """
# myapp/context_processors.py

from myapp.services.feature_flags import feature_flags

def feature_flags_context(request):
    '''Add feature flags to template context'''
    context = {
        'feature_flags': feature_flags,
        'user_segments': getattr(request, 'user_segments', {}),
        'user_id': getattr(request, 'user_id', 'anonymous')
    }
    
    # Add commonly used flags directly to context
    if hasattr(request, 'user_id'):
        user_id = request.user_id
        segments = getattr(request, 'user_segments', {})
        
        context.update({
            'show_new_ui': feature_flags.is_enabled(user_id, 'new_ui_enabled', segments=segments),
            'enable_dark_mode': feature_flags.is_enabled(user_id, 'dark_mode', segments=segments),
            'show_beta_features': feature_flags.is_enabled(user_id, 'beta_features', segments=segments),
        })
    
    return context

# Add to settings.py TEMPLATES:
# TEMPLATES = [
#     {
#         ...
#         'OPTIONS': {
#             'context_processors': [
#                 ...
#                 'myapp.context_processors.feature_flags_context',
#             ],
#         },
#     },
# ]
"""

# =============================================================================
# Template Tags
# =============================================================================

TEMPLATE_TAGS_EXAMPLE = """
# myapp/templatetags/feature_flags.py

from django import template
from myapp.services.feature_flags import feature_flags

register = template.Library()

@register.simple_tag(takes_context=True)
def feature_enabled(context, flag_name, default=False):
    '''Check if a feature flag is enabled for the current user'''
    request = context.get('request')
    if not request:
        return default
    
    user_id = getattr(request, 'user_id', 'anonymous')
    segments = getattr(request, 'user_segments', {})
    
    return feature_flags.is_enabled(user_id, flag_name, default, segments)

@register.simple_tag(takes_context=True)
def feature_value(context, flag_name, default=None):
    '''Get feature flag value for the current user'''
    request = context.get('request')
    if not request:
        return default
    
    user_id = getattr(request, 'user_id', 'anonymous')
    segments = getattr(request, 'user_segments', {})
    
    return feature_flags.get_flag_value(user_id, flag_name, default, segments)

@register.inclusion_tag('feature_flags/debug_panel.html', takes_context=True)
def feature_flags_debug(context):
    '''Debug panel showing all feature flags for current user'''
    request = context.get('request')
    if not request:
        return {'flags': {}}
    
    user_id = getattr(request, 'user_id', 'anonymous')
    segments = getattr(request, 'user_segments', {})
    
    user_flags = feature_flags.get_user_flags(user_id, segments)
    health = feature_flags.get_health_status()
    
    return {
        'user_id': user_id,
        'segments': segments,
        'flags': user_flags,
        'health': health,
        'debug': getattr(request, 'user', None) and getattr(request.user, 'is_staff', False)
    }
"""

# =============================================================================
# Views Examples
# =============================================================================

VIEWS_EXAMPLE = """
# myapp/views.py

from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from myapp.services.feature_flags import feature_flags

def home_view(request):
    '''Homepage with feature flag integration'''
    user_id = request.user_id
    segments = request.user_segments
    
    # Check various feature flags
    show_banner = feature_flags.is_enabled(user_id, 'homepage_banner', segments=segments)
    new_layout = feature_flags.is_enabled(user_id, 'new_homepage_layout', segments=segments)
    
    # Get configuration flags
    banner_config = feature_flags.get_flag_value(
        user_id, 'banner_config', 
        default={'text': 'Welcome!', 'color': 'blue'},
        segments=segments
    )
    
    template_name = 'home_new.html' if new_layout else 'home.html'
    
    context = {
        'show_banner': show_banner,
        'banner_config': banner_config,
        'new_layout': new_layout
    }
    
    return render(request, template_name, context)

@login_required
def dashboard_view(request):
    '''Dashboard with personalized feature flags'''
    user_id = str(request.user.id)
    segments = request.user_segments
    
    # Get all dashboard-related flags
    dashboard_flags = feature_flags.get_user_flags(
        user_id, 
        segments, 
        flag_keys=['dashboard_v2', 'analytics_panel', 'export_feature', 'real_time_updates']
    )
    
    # Configure dashboard based on flags
    context = {
        'use_v2_dashboard': dashboard_flags.get('dashboard_v2', False),
        'show_analytics': dashboard_flags.get('analytics_panel', False),
        'enable_export': dashboard_flags.get('export_feature', False),
        'real_time_updates': dashboard_flags.get('real_time_updates', False),
        'dashboard_flags': dashboard_flags
    }
    
    return render(request, 'dashboard.html', context)

@require_http_methods(["GET"])
def feature_flags_api(request):
    '''API endpoint to get feature flags for current user'''
    user_id = request.user_id
    segments = request.user_segments
    
    # Get specific flags requested
    flag_names = request.GET.get('flags', '').split(',')
    flag_names = [name.strip() for name in flag_names if name.strip()]
    
    if flag_names:
        flags = feature_flags.get_user_flags(user_id, segments, flag_names)
    else:
        flags = feature_flags.get_user_flags(user_id, segments)
    
    return JsonResponse({
        'user_id': user_id,
        'flags': flags,
        'segments': segments
    })

@login_required
def admin_feature_flags_status(request):
    '''Admin view to check feature flags status'''
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    health = feature_flags.get_health_status()
    
    return JsonResponse({
        'health': health,
        'timestamp': timezone.now().isoformat()
    })
"""

# =============================================================================
# Management Commands
# =============================================================================

MANAGEMENT_COMMAND_EXAMPLE = """
# myapp/management/commands/feature_flags_health.py

from django.core.management.base import BaseCommand
from myapp.services.feature_flags import feature_flags
import json

class Command(BaseCommand):
    help = 'Check FeatureFlagsHQ SDK health status'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            default='json',
            choices=['json', 'table'],
            help='Output format'
        )
    
    def handle(self, *args, **options):
        health = feature_flags.get_health_status()
        
        if options['format'] == 'json':
            self.stdout.write(json.dumps(health, indent=2))
        else:
            self.stdout.write("FeatureFlagsHQ SDK Health Status")
            self.stdout.write("=" * 40)
            for key, value in health.items():
                self.stdout.write(f"{key}: {value}")

# Usage: python manage.py feature_flags_health --format=table
"""

REFRESH_FLAGS_COMMAND = """
# myapp/management/commands/refresh_feature_flags.py

from django.core.management.base import BaseCommand
from myapp.services.feature_flags import feature_flags

class Command(BaseCommand):
    help = 'Manually refresh feature flags from server'
    
    def handle(self, *args, **options):
        self.stdout.write("Refreshing feature flags...")
        
        # This would work if the SDK was properly initialized
        # In this example, we're just showing the pattern
        try:
            success = feature_flags._sdk.refresh_flags() if feature_flags._sdk else False
            if success:
                self.stdout.write(
                    self.style.SUCCESS('Feature flags refreshed successfully')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('Failed to refresh feature flags')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error refreshing flags: {e}')
            )
"""

# =============================================================================
# Django App Configuration
# =============================================================================

APPS_CONFIG_EXAMPLE = """
# myapp/apps.py

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class MyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'
    
    def ready(self):
        '''Initialize feature flags service when Django starts'''
        try:
            from myapp.services.feature_flags import feature_flags
            # Service initialization happens automatically
            logger.info("FeatureFlagsHQ service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize FeatureFlagsHQ service: {e}")
    
    def shutdown(self):
        '''Clean shutdown of feature flags service'''
        try:
            from myapp.services.feature_flags import feature_flags
            feature_flags.shutdown()
            logger.info("FeatureFlagsHQ service shutdown complete")
        except Exception as e:
            logger.error(f"Error during FeatureFlagsHQ shutdown: {e}")
"""

# =============================================================================
# Template Examples
# =============================================================================

TEMPLATE_EXAMPLES = """
<!-- templates/base.html -->
{% load feature_flags %}

<!DOCTYPE html>
<html>
<head>
    <title>My App</title>
    {% feature_enabled 'css_optimization' as use_optimized_css %}
    {% if use_optimized_css %}
        <link rel="stylesheet" href="{% url 'optimized_css' %}">
    {% else %}
        <link rel="stylesheet" href="{% url 'regular_css' %}">
    {% endif %}
</head>
<body>
    {% feature_enabled 'new_header' as show_new_header %}
    {% if show_new_header %}
        {% include 'header_v2.html' %}
    {% else %}
        {% include 'header.html' %}
    {% endif %}
    
    <main>
        {% block content %}{% endblock %}
    </main>
    
    {% if user.is_staff %}
        {% feature_flags_debug %}
    {% endif %}
</body>
</html>

<!-- templates/dashboard.html -->
{% extends 'base.html' %}
{% load feature_flags %}

{% block content %}
<div class="dashboard">
    <h1>Dashboard</h1>
    
    {% feature_enabled 'analytics_panel' as show_analytics %}
    {% if show_analytics %}
        <div class="analytics-panel">
            {% include 'analytics_panel.html' %}
        </div>
    {% endif %}
    
    {% feature_value 'dashboard_layout' 'grid' as layout_type %}
    <div class="content layout-{{ layout_type }}">
        <!-- Dashboard content -->
    </div>
    
    {% feature_enabled 'export_feature' as can_export %}
    {% if can_export %}
        <button onclick="exportData()">Export Data</button>
    {% endif %}
</div>
{% endblock %}

<!-- templates/feature_flags/debug_panel.html -->
{% if debug %}
<div class="feature-flags-debug" style="position: fixed; bottom: 0; right: 0; background: #f0f0f0; padding: 10px; border: 1px solid #ccc; max-width: 300px;">
    <h4>Feature Flags Debug</h4>
    <p><strong>User:</strong> {{ user_id }}</p>
    <p><strong>SDK Status:</strong> {{ health.status }}</p>
    
    <h5>Segments:</h5>
    <ul>
        {% for key, value in segments.items %}
            <li>{{ key }}: {{ value }}</li>
        {% endfor %}
    </ul>
    
    <h5>Active Flags:</h5>
    <ul>
        {% for flag, value in flags.items %}
            <li>{{ flag }}: {{ value }}</li>
        {% endfor %}
    </ul>
</div>
{% endif %}
"""

# =============================================================================
# Testing Examples
# =============================================================================

TESTING_EXAMPLES = """
# tests/test_feature_flags.py

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from myapp.services.feature_flags import FeatureFlagService

class FeatureFlagTests(TestCase):
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
    
    @patch('myapp.services.feature_flags.create_production_client')
    def test_feature_flag_service_initialization(self, mock_client):
        '''Test feature flag service initializes correctly'''
        mock_sdk = MagicMock()
        mock_client.return_value = mock_sdk
        
        service = FeatureFlagService()
        self.assertIsNotNone(service)
    
    def test_user_context_extraction(self):
        '''Test user context extraction from request'''
        request = self.factory.get('/')
        request.user = self.user
        
        service = FeatureFlagService()
        context = service.get_user_context(request)
        
        self.assertIn('user_id', context)
        self.assertEqual(context['user_id'], str(self.user.id))
        self.assertIn('is_staff', context)
    
    @patch('myapp.services.feature_flags.feature_flags')
    def test_view_with_feature_flags(self, mock_flags):
        '''Test view behavior with feature flags'''
        mock_flags.is_enabled.return_value = True
        
        request = self.factory.get('/')
        request.user = self.user
        request.user_id = str(self.user.id)
        request.user_segments = {'subscription': 'premium'}
        
        from myapp.views import dashboard_view
        response = dashboard_view(request)
        
        self.assertEqual(response.status_code, 200)
        mock_flags.is_enabled.assert_called()

class FeatureFlagMiddlewareTests(TestCase):
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
    
    def test_middleware_adds_context(self):
        '''Test middleware adds feature flag context to request'''
        from myapp.middleware.feature_flags import FeatureFlagMiddleware
        
        middleware = FeatureFlagMiddleware(lambda r: None)
        request = self.factory.get('/')
        request.user = self.user
        
        middleware.process_request(request)
        
        self.assertTrue(hasattr(request, 'feature_flags'))
        self.assertTrue(hasattr(request, 'user_segments'))
        self.assertTrue(hasattr(request, 'user_id'))
"""

# =============================================================================
# Main Example Runner
# =============================================================================

def print_integration_guide():
    """Print the complete Django integration guide"""
    
    print("FeatureFlagsHQ SDK - Django Integration Guide")
    print("=" * 60)
    
    sections = [
        ("Django Settings Configuration", DJANGO_SETTINGS_EXAMPLE),
        ("Feature Flags Service", FEATURE_FLAGS_SERVICE),
        ("Django Middleware", MIDDLEWARE_EXAMPLE),
        ("Template Context Processor", CONTEXT_PROCESSOR_EXAMPLE),
        ("Template Tags", TEMPLATE_TAGS_EXAMPLE),
        ("Views Examples", VIEWS_EXAMPLE),
        ("Management Commands", MANAGEMENT_COMMAND_EXAMPLE),
        ("Refresh Flags Command", REFRESH_FLAGS_COMMAND),
        ("Django App Configuration", APPS_CONFIG_EXAMPLE),
        ("Template Examples", TEMPLATE_EXAMPLES),
        ("Testing Examples", TESTING_EXAMPLES),
    ]
    
    for title, content in sections:
        print(f"\n{'=' * 20}")
        print(f"{title}")
        print(f"{'=' * 20}")
        print(content)

def create_django_project_structure():
    """Instructions for setting up Django project structure"""
    
    structure = """
Django Project Structure:
========================

myproject/
├── myproject/
│   ├── settings.py              # Add FeatureFlagsHQ settings
│   ├── urls.py
│   └── wsgi.py
├── myapp/
│   ├── services/
│   │   └── feature_flags.py     # Main service class
│   ├── middleware/
│   │   └── feature_flags.py     # Django middleware
│   ├── templatetags/
│   │   └── feature_flags.py     # Template tags
│   ├── management/
│   │   └── commands/
│   │       ├── feature_flags_health.py
│   │       └── refresh_feature_flags.py
│   ├── context_processors.py    # Template context processor
│   ├── views.py                 # Views with feature flags
│   ├── apps.py                  # App configuration
│   └── tests/
│       └── test_feature_flags.py
├── templates/
│   ├── base.html               # Base template with flags
│   ├── dashboard.html          # Dashboard with flags
│   └── feature_flags/
│       └── debug_panel.html    # Debug panel template
├── requirements.txt            # Add featureflagshq-sdk
└── manage.py

Installation Steps:
==================

1. Install the SDK:
   pip install featureflagshq-sdk

2. Add to requirements.txt:
   featureflagshq-sdk>=1.0.0

3. Configure environment variables:
   export FEATUREFLAGSHQ_CLIENT_ID='your_client_id'
   export FEATUREFLAGSHQ_CLIENT_SECRET='your_client_secret'
   export FEATUREFLAGSHQ_ENVIRONMENT='production'

4. Update Django settings.py with the configuration above

5. Add middleware to MIDDLEWARE setting

6. Add context processor to TEMPLATES setting

7. Create the service, middleware, and template tags files

8. Run migrations if needed:
   python manage.py migrate

9. Test the integration:
   python manage.py feature_flags_health

Usage in Templates:
==================

{% load feature_flags %}

<!-- Simple flag check -->
{% feature_enabled 'new_ui' as show_new_ui %}
{% if show_new_ui %}
    <div class="new-ui">New UI Content</div>
{% endif %}

<!-- Get flag value -->
{% feature_value 'button_color' 'blue' as btn_color %}
<button style="background-color: {{ btn_color }}">Click Me</button>

<!-- Debug panel (for staff users) -->
{% if user.is_staff %}
    {% feature_flags_debug %}
{% endif %}

Usage in Views:
==============

def my_view(request):
    user_id = request.user_id
    segments = request.user_segments
    
    # Check feature flag
    new_feature = request.feature_flags.is_enabled(
        user_id, 'new_feature', segments=segments
    )
    
    # Get flag value
    config = request.feature_flags.get_flag_value(
        user_id, 'app_config', default={}, segments=segments
    )
    
    return render(request, 'template.html', {
        'new_feature': new_feature,
        'config': config
    })

API Integration:
===============

# Create API endpoint for frontend
@api_view(['GET'])
def get_user_flags(request):
    flags = request.feature_flags.get_user_flags(
        request.user_id, 
        request.user_segments
    )
    return Response({'flags': flags})

# Frontend usage
fetch('/api/user-flags/')
    .then(response => response.json())
    .then(data => {
        if (data.flags.new_ui_enabled) {
            enableNewUI();
        }
    });
"""
    
    print(structure)

if __name__ == "__main__":
    print_integration_guide()
    create_django_project_structure()