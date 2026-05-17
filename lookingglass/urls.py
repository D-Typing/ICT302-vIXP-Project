from django.urls import path

from . import views

app_name = "lookingglass"

urlpatterns = [
    path("", views.index, name="index"),
    path("summary/", views.summary, name="summary"),
    path("routes/", views.routes, name="routes"),
    path("neighbors/", views.neighbors, name="neighbors"),
]
