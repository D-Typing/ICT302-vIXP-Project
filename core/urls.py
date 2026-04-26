from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from pages.views import dashboard, documentation, peer_matrix, register

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard, name='dashboard'),
    path('login/', LoginView.as_view(template_name='pages/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', register, name='register'),
    path('docs/', documentation, name='documentation'),
    path('peers/', peer_matrix, name='peer_matrix'),
]
