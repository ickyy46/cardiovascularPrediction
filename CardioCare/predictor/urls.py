from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    # Web views
    path("", views.predict_cardio, name="predict_cardio"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("result/<int:pk>/", views.result_detail, name="result_detail"),
    path("result/anonymous/", views.anonymous_result, name="anonymous_result"),
    path("history/", views.prediction_history, name="prediction_history"),
    path("history/delete/<int:pk>/", views.delete_history, name="delete_history"),

    # Django Web Password Reset Views
    path("password-reset/", auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html"), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"), name="password_reset_done"),
    path("password-reset-confirm/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"), name="password_reset_confirm"),
    path("password-reset-complete/", auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"), name="password_reset_complete"),

    # REST API endpoints
    path("api/register/", views.api_register, name="api_register"),
    path("api/password-reset/", views.api_password_reset, name="api_password_reset"),
    path("api/predict/", views.api_predict_cardio, name="api_predict_cardio"),
    path("api/history/", views.api_prediction_history, name="api_prediction_history"),
]