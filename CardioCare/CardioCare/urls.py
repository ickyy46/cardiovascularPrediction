from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # Admin Interface
    path("admin/", admin.site.urls),

    # JWT Authentication Endpoints (Used by Flutter App Login)
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # App Routes (Includes Web views and /api/register/, /api/predict/, /api/history/)
    path("", include("predictor.urls")),
]