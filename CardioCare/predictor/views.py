from pathlib import Path
import warnings
import joblib
import numpy as np

from django.shortcuts import get_object_or_404, redirect, render
from sklearn.exceptions import InconsistentVersionWarning

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import CardioPrediction
from .serializers import CardioPredictionSerializer

warnings.filterwarnings('ignore', category=InconsistentVersionWarning)

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / 'ml' / 'cardio_model.pkl'
model = joblib.load(MODEL_PATH)


# ==========================================
# HELPER FUNCTION FOR ML PREDICTION LOGIC
# ==========================================
def calculate_cardio_risk(age, gender, weight, height, ap_hi, ap_lo, cholesterol, gluc, smoke, alco, active):
    """Calculates BMI, evaluates 10-feature array with ML model, and returns risk category."""
    height_m = height / 100.0
    bmi = round(weight / (height_m ** 2), 2) if height_m > 0 else 0.0

    # 10 features matching the trained model pipeline
    features = np.array([[
        age,
        gender,
        bmi,
        ap_hi,
        ap_lo,
        cholesterol,
        gluc,
        smoke,
        alco,
        active,
    ]])

    probabilities = model.predict_proba(features)[0]
    risk_percentage = round(probabilities[1] * 100, 1)

    if risk_percentage < 35.0:
        result = 'Lower Predicted Likelihood'
        result_class = 'success'
    elif risk_percentage < 65.0:
        result = 'Moderate Predicted Likelihood'
        result_class = 'warning'
    else:
        result = 'Higher Predicted Likelihood'
        result_class = 'danger'

    return bmi, risk_percentage, result, result_class


# ==========================================
# WEB VIEWS (HTML Templates)
# ==========================================
def predict_cardio(request):
    if request.method == 'POST':
        age = int(request.POST.get('age', 0))
        gender = int(request.POST.get('gender', 1))
        weight = float(request.POST.get('weight', 0))
        height = float(request.POST.get('height', 0))
        ap_hi = float(request.POST.get('ap_hi', 0))
        ap_lo = float(request.POST.get('ap_lo', 0))
        cholesterol = int(request.POST.get('cholesterol', 1))
        gluc = int(request.POST.get('gluc', 1))
        smoke = int(request.POST.get('smoke', 0))
        alco = int(request.POST.get('alco', 0))
        active = int(request.POST.get('active', 0))

        bmi, risk_percentage, result, result_class = calculate_cardio_risk(
            age, gender, weight, height, ap_hi, ap_lo, cholesterol, gluc, smoke, alco, active
        )

        record = CardioPrediction.objects.create(
            age=age,
            gender=gender,
            weight=weight,
            height=height,
            bmi=bmi,
            ap_hi=ap_hi,
            ap_lo=ap_lo,
            cholesterol=cholesterol,
            gluc=gluc,
            smoke=smoke,
            alco=alco,
            active=active,
            prediction_category=result,
            risk_percentage=risk_percentage,
        )

        # Redirect to the new dedicated result page
        return redirect('result_detail', pk=record.pk)

    return render(request, 'predictor/index.html')


def result_detail(request, pk):
    """Renders the result page component for a specific prediction record."""
    prediction = get_object_or_404(CardioPrediction, pk=pk)
    
    context = {
        'prediction': prediction,
        'prediction_date': prediction.created_at.strftime("%B %d, %Y") if hasattr(prediction, 'created_at') else None,
        'prediction_category': prediction.prediction_category.replace(' Predicted Likelihood', ''),
        'result': prediction.prediction_category,
        'risk_percentage': prediction.risk_percentage,
        'systolic': int(prediction.ap_hi),
        'diastolic': int(prediction.ap_lo),
        'cholesterol': prediction.cholesterol,
        'glucose': prediction.gluc,
        'age': prediction.age,
        'bmi': prediction.bmi,
        'physical_activity': prediction.active,
        'result_class': (
            'success' if 'Lower' in prediction.prediction_category
            else 'warning' if 'Moderate' in prediction.prediction_category
            else 'danger'
        ),
    }
    return render(request, 'predictor/components/result.html', context)

def prediction_history(request):
    history = CardioPrediction.objects.all().order_by('-created_at')
    return render(request, 'predictor/history.html', {'history': history})


def delete_history(request, pk):
    record = get_object_or_404(CardioPrediction, pk=pk)
    record.delete()
    return redirect('prediction_history')


# ==========================================
# REST API ENDPOINTS (Protected with JWT Auth)
# ==========================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_predict_cardio(request):
    """API Endpoint to predict cardiovascular risk via JSON POST payload."""
    serializer = CardioPredictionSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data

        bmi, risk_percentage, result_category, _ = calculate_cardio_risk(
            age=data['age'],
            gender=data['gender'],
            weight=data['weight'],
            height=data['height'],
            ap_hi=data['ap_hi'],
            ap_lo=data['ap_lo'],
            cholesterol=data['cholesterol'],
            gluc=data['gluc'],
            smoke=data['smoke'],
            alco=data['alco'],
            active=data['active']
        )

        user = request.user if request.user.is_authenticated else None

        record = serializer.save(
            bmi=bmi,
            prediction_category=result_category,
            risk_percentage=risk_percentage
        )

        return Response({
            "id": record.id,
            "user": user.username if user else "Anonymous",
            "bmi": bmi,
            "prediction_category": result_category,
            "risk_percentage": risk_percentage,
            "disclaimer": "This application is a home-based preliminary risk screening tool and does not constitute a medical diagnosis."
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_prediction_history(request):
    """API Endpoint to fetch prediction history for authenticated mobile applications."""
    records = CardioPrediction.objects.all().order_by('-created_at')
    serializer = CardioPredictionSerializer(records, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)