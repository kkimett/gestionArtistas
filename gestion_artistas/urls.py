from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from artists.views import ArtistListView

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html", redirect_authenticated_user=True),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", ArtistListView.as_view(), name="dashboard-home"),
    path("artists/", include("artists.urls")),
    path("billing/", include("billing.urls")),
]
