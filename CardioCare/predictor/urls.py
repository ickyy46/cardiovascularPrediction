from django.urls import path
from . import views

urlpatterns = [
    path("", views.predict_cardio, name="predict_cardio"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("result/<int:pk>/", views.result_detail, name="result_detail"),
    path("result/anonymous/", views.anonymous_result, name="anonymous_result"),
    path("history/", views.prediction_history, name="prediction_history"),
    path("history/delete/<int:pk>/", views.delete_history, name="delete_history"),
    path("api/predict/", views.api_predict_cardio, name="api_predict_cardio"),
    path("api/history/", views.api_prediction_history, name="api_prediction_history"),
]
