from django.urls import path
from . import views

urlpatterns = [
    path('', views.predict_cardio, name='predict_cardio'),
path('result/<int:pk>/', views.result_detail, name='result_detail'),
    path('history/', views.prediction_history, name='prediction_history'),
    path('history/delete/<int:pk>/', views.delete_history, name='delete_history'),
    
    # API Endpoints
    path('api/predict/', views.api_predict_cardio, name='api_predict_cardio'),
    path('api/history/', views.api_prediction_history, name='api_prediction_history'),
]