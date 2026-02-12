"""
Django URL configuration fixture for testing the DjangoRoutesParser.

Defines URL patterns using path(), re_path(), include(), and
Django REST Framework router registrations to exercise all
detection paths in the parser.
"""

from django.urls import path, re_path, include
from rest_framework.routers import DefaultRouter

from . import views
from .viewsets import ArticleViewSet


# --- DRF Router ---
router = DefaultRouter()
router.register(r'articles', ArticleViewSet, basename='article')

# --- URL Patterns ---
urlpatterns = [
    # Direct view function routes
    path('', views.home, name='home'),
    path('about/', views.about_page, name='about'),

    # Route with path converter parameters
    path('users/<int:user_id>/', views.user_detail, name='user-detail'),
    path('posts/<slug:post_slug>/', views.post_detail, name='post-detail'),

    # Include app-level URLs with namespace
    path('api/v1/', include(('myapp.api_urls', 'myapp'), namespace='api-v1')),

    # Include router URLs
    path('api/v1/', include(router.urls)),

    # Include another app
    path('blog/', include('blog.urls')),

    # Regex path for backwards compatibility
    re_path(r'^legacy/user/(?P<username>\w+)/$', views.legacy_user_profile, name='legacy-user'),
]

# Augmented assignment pattern
urlpatterns += [
    path('health/', views.health_check, name='health-check'),
]
