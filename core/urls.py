from django.contrib import admin
from django.urls import path
from pages import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),
    path('docs/', views.documentation, name='documentation'),
    path('peers/', views.peer_matrix, name='peer_matrix'),
]
