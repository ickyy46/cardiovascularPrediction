from django.urls import path
from . import views

urlpatterns = [
    path("", views.predict_cardio, name="predict_cardio"),
    path("history/", views.prediction_history, name="prediction_history"),
    path("delete/<int:pk>/", views.delete_history, name="delete_cardio_history"),
    path("api/predict/", views.api_predict_cardio, name="api_predict_cardio"),
    path("api/history/", views.api_prediction_history, name="api_prediction_history"),
]