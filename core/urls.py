from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path

from pages.views import PortalLoginView, admin_hub, dashboard, documentation, home, peer_matrix, register

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('dashboard/', dashboard, name='dashboard'),
    path('login/', PortalLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', register, name='register'),
    path('docs/', documentation, name='documentation'),
    path('peers/', peer_matrix, name='peer_matrix'),
    path('admin-hub/', admin_hub, name='admin_hub'),
    path('looking-glass/', include('lookingglass.urls')),
]
