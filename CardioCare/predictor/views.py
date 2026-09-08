from pathlib import Path
import warnings

import joblib
import numpy as np
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from sklearn.exceptions import InconsistentVersionWarning
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import RegisterForm
from .models import CardioPrediction
from .serializers import CardioPredictionSerializer

warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "ml" / "cardio_model.pkl"
model = joblib.load(MODEL_PATH)


def calculate_cardio_risk(age, gender, weight, height, ap_hi, ap_lo, cholesterol, gluc, smoke, alco, active):
    height_m = height / 100.0
    bmi = round(weight / (height_m ** 2), 2)

    features = np.array([[
        age, gender, bmi, ap_hi, ap_lo,
        cholesterol, gluc, smoke, alco, active,
    ]], dtype=float)

    probabilities = model.predict_proba(features)[0]
    risk_percentage = round(float(probabilities[1]) * 100, 1)

    if risk_percentage < 35.0:
        result = "Lower Predicted Likelihood"
    elif risk_percentage < 65.0:
        result = "Moderate Predicted Likelihood"
    else:
        result = "Higher Predicted Likelihood"

    return bmi, risk_percentage, result


def _choice_label(value, choices):
    return dict(choices).get(int(value), str(value))


def _result_context(data, request=None):
    category = data["prediction_category"]
    return {
        "prediction": data.get("prediction"),
        "prediction_date": data.get("prediction_date"),
        "prediction_category": category.replace(" Predicted Likelihood", ""),
        "result": category,
        "risk_percentage": data["risk_percentage"],
        "systolic": int(float(data["ap_hi"])),
        "diastolic": int(float(data["ap_lo"])),
        "cholesterol": _choice_label(data["cholesterol"], CardioPrediction._meta.get_field("cholesterol").choices),
        "glucose": _choice_label(data["gluc"], CardioPrediction._meta.get_field("gluc").choices),
        "age": data["age"],
        "gender": int(data["gender"]),
        "weight": data["weight"],
        "height": data["height"],
        "bmi": data["bmi"],
        "physical_activity": "Yes" if int(data["active"]) else "No",
        "smoking": "Yes" if int(data["smoke"]) else "No",
        "alcohol": "Yes" if int(data["alco"]) else "No",
        "genetic": int(data.get("genetic", 0)),
        "is_authenticated": bool(request and request.user.is_authenticated),
    }


def _parse_assessment(post):
    data = {
        "age": int(post.get("age", "")),
        "gender": int(post.get("gender", "")),
        "weight": float(post.get("weight", "")),
        "height": float(post.get("height", "")),
        "ap_hi": float(post.get("ap_hi", "")),
        "ap_lo": float(post.get("ap_lo", "")),
        "cholesterol": int(post.get("cholesterol", "")),
        "gluc": int(post.get("gluc", "")),
        "smoke": int(post.get("smoke", "")),
        "alco": int(post.get("alco", "")),
        "active": int(post.get("active", "")),
        "genetic": int(post.get("genetic", "0")),
    }

    if not 18 <= data["age"] <= 120:
        raise ValueError("Age must be between 18 and 120 years.")
    if data["gender"] not in (1, 2):
        raise ValueError("Please select a valid sex.")
    if not 30 <= data["weight"] <= 300:
        raise ValueError("Weight must be between 30 and 300 kg.")
    if not 100 <= data["height"] <= 250:
        raise ValueError("Height must be between 100 and 250 cm.")
    if not 70 <= data["ap_hi"] <= 250:
        raise ValueError("Systolic blood pressure must be between 70 and 250 mmHg.")
    if not 40 <= data["ap_lo"] <= 150:
        raise ValueError("Diastolic blood pressure must be between 40 and 150 mmHg.")
    if data["ap_lo"] >= data["ap_hi"]:
        raise ValueError("Systolic blood pressure must be higher than diastolic blood pressure.")
    if data["cholesterol"] not in (1, 2, 3) or data["gluc"] not in (1, 2, 3):
        raise ValueError("Please select valid cholesterol and glucose levels.")
    if any(data[key] not in (0, 1) for key in ("smoke", "alco", "active", "genetic")):
        raise ValueError("Please select valid lifestyle values.")

    return data


def predict_cardio(request):
    if request.method == "POST":
        try:
            data = _parse_assessment(request.POST)
            bmi, risk_percentage, result = calculate_cardio_risk(
                data["age"], data["gender"], data["weight"], data["height"],
                data["ap_hi"], data["ap_lo"], data["cholesterol"], data["gluc"],
                data["smoke"], data["alco"], data["active"],
            )
            data.update({
                "bmi": bmi,
                "prediction_category": result,
                "risk_percentage": risk_percentage,
            })

            if request.user.is_authenticated:
                record = CardioPrediction.objects.create(user=request.user, **data)
                request.session.pop("anonymous_result", None)
                return redirect("result_detail", pk=record.pk)

            # Anonymous flow: keep only one temporary result in the session.
            # No CardioPrediction database row is created.
            data["prediction_date"] = timezone.localtime().strftime("%B %d, %Y %I:%M %p")
            request.session["anonymous_result"] = data
            request.session.modified = True
            return redirect("anonymous_result")

        except (TypeError, ValueError) as exc:
            messages.error(request, str(exc) or "Please enter valid values for all assessment fields.")
        except Exception:
            messages.error(request, "The assessment could not be generated. Please check your inputs and try again.")

    return render(request, "predictor/index.html", {"show_form": request.method == "POST"})


@login_required
def result_detail(request, pk):
    prediction = get_object_or_404(CardioPrediction, pk=pk, user=request.user)
    context = _result_context({
        "prediction": prediction,
        "prediction_date": timezone.localtime(prediction.created_at).strftime("%B %d, %Y %I:%M %p"),
        "prediction_category": prediction.prediction_category,
        "risk_percentage": prediction.risk_percentage,
        "ap_hi": prediction.ap_hi,
        "ap_lo": prediction.ap_lo,
        "cholesterol": prediction.cholesterol,
        "gluc": prediction.gluc,
        "age": prediction.age,
        "gender": prediction.gender,
        "weight": prediction.weight,
        "height": prediction.height,
        "bmi": prediction.bmi,
        "active": prediction.active,
        "smoke": prediction.smoke,
        "alco": prediction.alco,
        "genetic": prediction.genetic,
    }, request=request)
    return render(request, "predictor/components/result.html", context)


def anonymous_result(request):
    data = request.session.get("anonymous_result")
    if not data:
        messages.info(request, "Start an assessment to generate a result.")
        return redirect("predict_cardio")
    return render(request, "predictor/components/result.html", _result_context(data, request=request))


@login_required
def prediction_history(request):
    history = CardioPrediction.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "predictor/history.html", {"history": history})


@login_required
def delete_history(request, pk):
    record = get_object_or_404(CardioPrediction, pk=pk, user=request.user)
    if request.method == "POST":
        record.delete()
        messages.success(request, "Prediction deleted from your history.")
    return redirect("prediction_history")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("predict_cardio")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            request.session.pop("anonymous_result", None)
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
        request.session.pop("anonymous_result", None)
        messages.success(request, f"Welcome back, {form.get_user().username}!")
        return redirect(request.GET.get("next") or "predict_cardio")
    return render(request, "registration/login.html", {"form": form})


def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, "You have been logged out.")
    return redirect("predict_cardio")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_predict_cardio(request):
    serializer = CardioPredictionSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        bmi, risk_percentage, result_category = calculate_cardio_risk(
            data["age"], data["gender"], data["weight"], data["height"],
            data["ap_hi"], data["ap_lo"], data["cholesterol"], data["gluc"],
            data["smoke"], data["alco"], data["active"],
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
