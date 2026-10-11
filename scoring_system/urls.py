"""
URL configuration for scoring_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('', include('competitions.urls')),
    path('', include('participants.urls')),
    path('', include('teams.urls')),
    path('', include('judges.urls')),
    path('', include('scoring.urls')),
    path('', include('sports.urls')),
    path('', include('eligibility.urls')),
    path('', include('announcements.urls')),
    path('', include('registrations.urls')),
    path('', include('protests.urls')),
    path('', include('audit.urls')),
    path('', include('reports.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
