from pathlib import Path
import warnings
import joblib
import numpy as np

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from sklearn.exceptions import InconsistentVersionWarning

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .forms import RegisterForm
from .models import CardioPrediction
from .serializers import CardioPredictionSerializer

warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "ml" / "cardio_model.pkl"
model = joblib.load(MODEL_PATH)


def calculate_cardio_risk(age, gender, weight, height, ap_hi, ap_lo, cholesterol, gluc, smoke, alco, active):
    height_m = height / 100.0
    bmi = round(weight / (height_m ** 2), 2) if height_m > 0 else 0.0

    features = np.array([[
        age, gender, bmi, ap_hi, ap_lo,
        cholesterol, gluc, smoke, alco, active,
    ]])

    probabilities = model.predict_proba(features)[0]
    risk_percentage = round(probabilities[1] * 100, 1)

    if risk_percentage < 35.0:
        result = "Lower Predicted Likelihood"
        result_class = "success"
    elif risk_percentage < 65.0:
        result = "Moderate Predicted Likelihood"
        result_class = "warning"
    else:
        result = "Higher Predicted Likelihood"
        result_class = "danger"

    return bmi, risk_percentage, result, result_class


def _result_context(data):
    category = data["prediction_category"]
    return {
        "prediction": data.get("prediction"),
        "prediction_date": data.get("prediction_date"),
        "prediction_category": category.replace(" Predicted Likelihood", ""),
        "result": category,
        "risk_percentage": data["risk_percentage"],
        "systolic": int(data["ap_hi"]),
        "diastolic": int(data["ap_lo"]),
        "cholesterol": data["cholesterol"],
        "glucose": data["gluc"],
        "age": data["age"],
        "bmi": data["bmi"],
        "physical_activity": data["active"],
        "genetic": data.get("genetic", 0),
        "result_class": (
            "success" if "Lower" in category
            else "warning" if "Moderate" in category
            else "danger"
        ),
    }


def predict_cardio(request):
    if request.method == "POST":
        try:
            age = int(request.POST.get("age", 0))
            gender = int(request.POST.get("gender", request.POST.get("sex", 1)))
            weight = float(request.POST.get("weight", 0))
            height = float(request.POST.get("height", 0))
            ap_hi = float(request.POST.get("ap_hi", request.POST.get("systolic", 0)))
            ap_lo = float(request.POST.get("ap_lo", request.POST.get("diastolic", 0)))
            cholesterol = int(request.POST.get("cholesterol", 1))
            gluc = int(request.POST.get("gluc", request.POST.get("glucose", 1)))
            smoke = int(request.POST.get("smoke", request.POST.get("smoking", 0)))
            alco = int(request.POST.get("alco", request.POST.get("lifestyle", 0)))
            active = int(request.POST.get("active", request.POST.get("physical_activity", 0)))
            genetic = int(request.POST.get("genetic", 0))

            # The model expects binary smoke/alcohol/activity values.
            smoke = 1 if smoke > 0 else 0
            alco = 1 if alco > 0 else 0
            active = 1 if active > 0 else 0

            bmi, risk_percentage, result, _ = calculate_cardio_risk(
                age, gender, weight, height, ap_hi, ap_lo,
                cholesterol, gluc, smoke, alco, active
            )

            data = {
                "age": age, "gender": gender, "weight": weight, "height": height,
                "bmi": bmi, "ap_hi": ap_hi, "ap_lo": ap_lo,
                "cholesterol": cholesterol, "gluc": gluc,
                "smoke": smoke, "alco": alco, "active": active,
                "genetic": genetic, "prediction_category": result,
                "risk_percentage": risk_percentage,
            }

            if request.user.is_authenticated:
                record = CardioPrediction.objects.create(user=request.user, **data)
                return redirect("result_detail", pk=record.pk)

            # Anonymous users get the result, but nothing is written to the database.
            request.session["anonymous_result"] = data
            return redirect("anonymous_result")

        except (TypeError, ValueError, ZeroDivisionError):
            messages.error(request, "Please enter valid values for all assessment fields.")

    return render(request, "predictor/index.html")


@login_required
def result_detail(request, pk):
    prediction = get_object_or_404(CardioPrediction, pk=pk, user=request.user)
    context = _result_context({
        "prediction": prediction,
        "prediction_date": prediction.created_at.strftime("%B %d, %Y"),
        "prediction_category": prediction.prediction_category,
        "risk_percentage": prediction.risk_percentage,
        "ap_hi": prediction.ap_hi,
        "ap_lo": prediction.ap_lo,
        "cholesterol": prediction.cholesterol,
        "gluc": prediction.gluc,
        "age": prediction.age,
        "bmi": prediction.bmi,
        "active": prediction.active,
        "genetic": 0,
    })
    return render(request, "predictor/components/result.html", context)


def anonymous_result(request):
    data = request.session.get("anonymous_result")
    if not data:
        return redirect("predict_cardio")
    return render(
        request,
        "predictor/components/result.html",
        _result_context(data),
    )


@login_required
def prediction_history(request):
    history = CardioPrediction.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "predictor/history.html", {"history": history})


@login_required
def delete_history(request, pk):
    record = get_object_or_404(CardioPrediction, pk=pk, user=request.user)
    if request.method == "POST":
        record.delete()
        messages.success(request, "Prediction deleted.")
    return redirect("prediction_history")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("predict_cardio")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to CardioCare, {user.username}!")
            return redirect("predict_cardio")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("predict_cardio")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get("next") or "predict_cardio")
    return render(request, "registration/login.html", {"form": form})


def logout_view(request):
    if request.method == "POST":
        logout(request)
    return redirect("predict_cardio")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_predict_cardio(request):
    serializer = CardioPredictionSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        bmi, risk_percentage, result_category, _ = calculate_cardio_risk(
            data["age"], data["gender"], data["weight"], data["height"],
            data["ap_hi"], data["ap_lo"], data["cholesterol"],
            data["gluc"], data["smoke"], data["alco"], data["active"]
        )
        record = serializer.save(
            user=request.user,
            bmi=bmi,
            prediction_category=result_category,
            risk_percentage=risk_percentage,
        )
        return Response({
            "id": record.id,
            "user": request.user.username,
            "bmi": bmi,
            "prediction_category": result_category,
            "risk_percentage": risk_percentage,
            "disclaimer": "This application is a home-based preliminary risk screening tool and does not constitute a medical diagnosis.",
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_prediction_history(request):
    records = CardioPrediction.objects.filter(user=request.user).order_by("-created_at")
    serializer = CardioPredictionSerializer(records, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
