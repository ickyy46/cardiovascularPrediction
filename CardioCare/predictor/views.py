from pathlib import Path
import warnings

import joblib
import numpy as np

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from sklearn.exceptions import InconsistentVersionWarning

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .forms import AdminUserCreateForm, AdminUserEditForm, RegisterForm
from .models import CardioPrediction
from .serializers import CardioPredictionSerializer


warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "ml" / "cardio_model.pkl"
# model = joblib.load(MODEL_PATH)

def get_model():
  global _model
  if _model is None:
    _model = joblib.load(MODEL_PATH)
  return _model


# =========================================================
# CARDIOVASCULAR RISK CALCULATION
# =========================================================

def calculate_cardio_risk(
    age,
    gender,
    weight,
    height,
    ap_hi,
    ap_lo,
    cholesterol,
    gluc,
    smoke,
    alco,
    active,
):
    height_m = height / 100.0
    bmi = round(weight / (height_m ** 2), 2)

    features = np.array(
        [[
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
        ]],
        dtype=float,
    )

    loaded_model = get_model()
    probabilities = loaded_model.predict_proba(features)[0]
    risk_percentage = round(float(probabilities[1]) * 100, 1)

    if risk_percentage < 35.0:
        result = "Lower Predicted Likelihood"
    elif risk_percentage < 65.0:
        result = "Moderate Predicted Likelihood"
    else:
        result = "Higher Predicted Likelihood"

    return bmi, risk_percentage, result

def get_risk_factors(data):
    factors = []
    if float(data['ap_hi']) >= 130 or float(data['ap_lo']) >= 80:
        factors.append("Elevated blood pressure reading (Hypertension risk)")
    if float(data['bmi']) >= 25.0:
        factors.append(f"BMI elevated at {data['bmi']} (Overweight range)")
    if int(data['cholesterol']) > 1:
        factors.append("Above normal serum cholesterol levels")
    if int(data['gluc']) > 1:
        factors.append("Above normal glucose levels")
    if int(data['smoke']) == 1:
        factors.append("Active tobacco smoking habit")
    if int(data['active']) == 0:
        factors.append("Lack of regular physical activity")
    return factors


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def _choice_label(value, choices):
    return dict(choices).get(int(value), str(value))


def _result_context(data, request=None):
    category = data["prediction_category"]

    # --- EXPLAINABLE AI: Contributing Factor Analysis ---
    reasons = []
    ap_hi = float(data.get("ap_hi", 0))
    ap_lo = float(data.get("ap_lo", 0))
    bmi = float(data.get("bmi", 0))
    chol = int(data.get("cholesterol", 1))
    gluc = int(data.get("gluc", 1))
    smoke = int(data.get("smoke", 0))
    active = int(data.get("active", 1))

    if ap_hi >= 130 or ap_lo >= 80:
        reasons.append(
            f"Elevated blood pressure ({int(ap_hi)}/{int(ap_lo)} mmHg) suggests"
            " stage hypertension risk."
        )
    if bmi >= 25.0:
        reasons.append(
            f"BMI of {bmi} falls into the overweight or higher range, increasing"
            " cardiac strain."
        )
    if chol > 1:
        reasons.append(
            "Serum cholesterol is above normal limits, which can contribute to"
            " arterial plaque."
        )
    if gluc > 1:
        reasons.append(
            "Blood glucose reading is above optimal reference thresholds."
        )
    if smoke == 1:
        reasons.append(
            "Active tobacco use constricts vessels and accelerates cardiovascular"
            " risk."
        )
    if active == 0:
        reasons.append(
            "Sedentary lifestyle flagged; regular physical activity lowers"
            " baseline risk."
        )

    return {
        "prediction": data.get("prediction"),
        "prediction_date": data.get("prediction_date"),
        "prediction_category": category.replace(" Predicted Likelihood", ""),
        "result": category,
        "risk_percentage": data["risk_percentage"],
        "risk_reasons": reasons,  # <-- Added for Explainable AI
        "systolic": int(float(data["ap_hi"])),
        "diastolic": int(float(data["ap_lo"])),
        "cholesterol": _choice_label(
            data["cholesterol"],
            CardioPrediction._meta.get_field("cholesterol").choices,
        ),
        "glucose": _choice_label(
            data["gluc"], CardioPrediction._meta.get_field("gluc").choices
        ),
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
        raise ValueError(
            "Systolic blood pressure must be between 70 and 250 mmHg."
        )

    if not 40 <= data["ap_lo"] <= 150:
        raise ValueError(
            "Diastolic blood pressure must be between 40 and 150 mmHg."
        )

    if data["ap_lo"] >= data["ap_hi"]:
        raise ValueError(
            "Systolic blood pressure must be higher than "
            "diastolic blood pressure."
        )

    if (
        data["cholesterol"] not in (1, 2, 3)
        or data["gluc"] not in (1, 2, 3)
    ):
        raise ValueError(
            "Please select valid cholesterol and glucose levels."
        )

    if any(
        data[key] not in (0, 1)
        for key in ("smoke", "alco", "active", "genetic")
    ):
        raise ValueError("Please select valid lifestyle values.")

    return data


# =========================================================
# MAIN ASSESSMENT
# =========================================================

def predict_cardio(request):
    if request.method == "POST":
        try:
            data = _parse_assessment(request.POST)

            bmi, risk_percentage, result = calculate_cardio_risk(
                data["age"],
                data["gender"],
                data["weight"],
                data["height"],
                data["ap_hi"],
                data["ap_lo"],
                data["cholesterol"],
                data["gluc"],
                data["smoke"],
                data["alco"],
                data["active"],
            )

            data.update(
                {
                    "bmi": bmi,
                    "prediction_category": result,
                    "risk_percentage": risk_percentage,
                }
            )

            # Logged-in user:
            # save result into database/history.
            if request.user.is_authenticated:
                record = CardioPrediction.objects.create(
                    user=request.user,
                    **data,
                )

                request.session.pop(
                    "anonymous_result",
                    None,
                )

                return redirect(
                    "result_detail",
                    pk=record.pk,
                )

            # Anonymous user:
            # show result but do NOT save to database.
            data["prediction_date"] = (
                timezone.localtime().strftime(
                    "%B %d, %Y %I:%M %p"
                )
            )

            request.session["anonymous_result"] = data
            request.session.modified = True

            return redirect("anonymous_result")

        except (TypeError, ValueError) as exc:
            messages.error(
                request,
                str(exc)
                or "Please enter valid values for all assessment fields.",
            )

        except Exception:
            messages.error(
                request,
                "The assessment could not be generated. "
                "Please check your inputs and try again.",
            )

    return render(
        request,
        "predictor/index.html",
        {
            "show_form": request.method == "POST",
        },
    )


# =========================================================
# RESULT
# =========================================================

@login_required
def result_detail(request, pk):
    prediction = get_object_or_404(
        CardioPrediction,
        pk=pk,
        user=request.user,
    )

    context = _result_context(
        {
            "prediction": prediction,
            "prediction_date": timezone.localtime(
                prediction.created_at
            ).strftime(
                "%B %d, %Y %I:%M %p"
            ),
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
        },
        request=request,
    )

    return render(
        request,
        "predictor/components/result.html",
        context,
    )


def anonymous_result(request):
    data = request.session.get("anonymous_result")

    if not data:
        messages.info(
            request,
            "Start an assessment to generate a result.",
        )
        return redirect("predict_cardio")

    return render(
        request,
        "predictor/components/result.html",
        _result_context(
            data,
            request=request,
        ),
    )


# =========================================================
# USER HISTORY
# =========================================================

@login_required
def prediction_history(request):
    history = CardioPrediction.objects.filter(
        user=request.user
    ).order_by(
        "-created_at"
    )

    return render(
        request,
        "predictor/history.html",
        {
            "history": history,
        },
    )


@login_required
def delete_history(request, pk):
    record = get_object_or_404(
        CardioPrediction,
        pk=pk,
        user=request.user,
    )

    if request.method == "POST":
        record.delete()

        messages.success(
            request,
            "Prediction deleted from your history.",
        )

    return redirect("prediction_history")


# =========================================================
# SUPERUSER / ADMIN PERMISSION
# =========================================================

def _is_superuser(user):
    return (
        user.is_authenticated
        and user.is_superuser
    )


superuser_required = user_passes_test(
    _is_superuser,
    login_url="login",
)


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@superuser_required
def system_admin_dashboard(request):
    context = {
        "total_users": User.objects.count(),
        "active_users": User.objects.filter(
            is_active=True
        ).count(),
        "superusers": User.objects.filter(
            is_superuser=True
        ).count(),
        "total_predictions": CardioPrediction.objects.count(),
        "recent_users": User.objects.order_by(
            "-date_joined"
        )[:5],
        "recent_predictions": (
            CardioPrediction.objects
            .select_related("user")
            .order_by("-created_at")[:5]
        ),
    }

    return render(
        request,
        "predictor/admin/dashboard.html",
        context,
    )


# =========================================================
# ADMIN - MANAGE USERS
# =========================================================

@superuser_required
def system_admin_users(request):
    users = User.objects.order_by(
        "-is_superuser",
        "-is_staff",
        "username",
    )

    return render(
        request,
        "predictor/admin/users.html",
        {
            "users": users,
        },
    )


@superuser_required
def system_admin_user_create(request):
    if request.method == "POST":
        form = AdminUserCreateForm(
            request.POST
        )

        if form.is_valid():
            user = form.save()

            messages.success(
                request,
                f"User {user.username} created successfully.",
            )

            return redirect(
                "system_admin_users"
            )

    else:
        form = AdminUserCreateForm()

    return render(
        request,
        "predictor/admin/user_form.html",
        {
            "form": form,
            "form_title": "Create User",
        },
    )


@superuser_required
def system_admin_user_edit(
    request,
    user_id,
):
    target = get_object_or_404(
        User,
        pk=user_id,
    )

    if request.method == "POST":
        form = AdminUserEditForm(
            request.POST,
            instance=target,
        )

        if form.is_valid():
            edited = form.save(
                commit=False
            )

            # Prevent current admin from
            # removing own admin access.
            if target.pk == request.user.pk:
                edited.is_active = True
                edited.is_staff = True
                edited.is_superuser = True

            edited.save()

            messages.success(
                request,
                f"User {edited.username} updated successfully.",
            )

            return redirect(
                "system_admin_users"
            )

    else:
        form = AdminUserEditForm(
            instance=target
        )

    return render(
        request,
        "predictor/admin/user_form.html",
        {
            "form": form,
            "form_title": (
                f"Edit User: {target.username}"
            ),
            "target_user": target,
        },
    )


@superuser_required
def system_admin_user_delete(
    request,
    user_id,
):
    target = get_object_or_404(
        User,
        pk=user_id,
    )

    if target.pk == request.user.pk:
        messages.error(
            request,
            "You cannot delete your own "
            "administrator account while signed in.",
        )

        return redirect(
            "system_admin_users"
        )

    if request.method == "POST":
        username = target.username

        target.delete()

        messages.success(
            request,
            f"User {username} deleted successfully.",
        )

    return redirect(
        "system_admin_users"
    )


# =========================================================
# ADMIN - DATABASE / PREDICTION RECORDS
# =========================================================

@superuser_required
def system_admin_predictions(request):
    predictions = (
        CardioPrediction.objects
        .select_related("user")
        .order_by("-created_at")
    )

    return render(
        request,
        "predictor/admin/predictions.html",
        {
            "predictions": predictions,
        },
    )


@superuser_required
def system_admin_prediction_delete(
    request,
    pk,
):
    record = get_object_or_404(
        CardioPrediction,
        pk=pk,
    )

    if request.method == "POST":
        record.delete()

        messages.success(
            request,
            "Prediction record deleted successfully.",
        )

    return redirect(
        "system_admin_predictions"
    )


# =========================================================
# REGISTER
# =========================================================

def register_view(request):
    if request.user.is_authenticated:
        return redirect(
            "predict_cardio"
        )

    if request.method == "POST":
        form = RegisterForm(
            request.POST
        )

        if form.is_valid():
            user = form.save()

            login(
                request,
                user,
            )

            request.session.pop(
                "anonymous_result",
                None,
            )

            messages.success(
                request,
                f"Welcome to CardioCare, {user.username}!",
            )

            return redirect(
                "predict_cardio"
            )

    else:
        form = RegisterForm()

    return render(
        request,
        "registration/register.html",
        {
            "form": form,
        },
    )


# =========================================================
# LOGIN
# =========================================================

def login_view(request):
    if request.user.is_authenticated:
        return redirect(
            "predict_cardio"
        )

    form = AuthenticationForm(
        request,
        data=request.POST or None,
    )

    if (
        request.method == "POST"
        and form.is_valid()
    ):
        user = form.get_user()

        login(
            request,
            user,
        )

        request.session.pop(
            "anonymous_result",
            None,
        )

        messages.success(
            request,
            f"Welcome back, {user.username}!",
        )

        return redirect(
            request.GET.get("next")
            or "predict_cardio"
        )

    return render(
        request,
        "registration/login.html",
        {
            "form": form,
        },
    )


# =========================================================
# LOGOUT
# =========================================================

def logout_view(request):
    if request.user.is_authenticated:
        logout(request)

        messages.success(
            request,
            "You have been logged out.",
        )

    return redirect(
        "predict_cardio"
    )


# =========================================================
# API - REGISTER
# =========================================================

@api_view(["POST"])
@permission_classes([AllowAny])
def api_register(request):
    username = request.data.get(
        "username"
    )
    email = request.data.get(
        "email"
    )
    password = request.data.get(
        "password"
    )

    if (
        not username
        or not email
        or not password
    ):
        return Response(
            {
                "error": (
                    "Username, email, "
                    "and password are required."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(
        username=username
    ).exists():
        return Response(
            {
                "error": (
                    "A user with that username "
                    "already exists."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(
        email=email
    ).exists():
        return Response(
            {
                "error": (
                    "A user with that email "
                    "address already exists."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    User.objects.create_user(
        username=username,
        email=email,
        password=password,
    )

    return Response(
        {
            "message": (
                "User registered successfully."
            )
        },
        status=status.HTTP_201_CREATED,
    )


# =========================================================
# API - PASSWORD RESET
# =========================================================

@api_view(["POST"])
@permission_classes([AllowAny])
def api_password_reset(request):
    email = request.data.get(
        "email"
    )

    if not email:
        return Response(
            {
                "error": (
                    "Email address is required."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    users = User.objects.filter(
        email=email
    )

    if users.exists():
        for user in users:
            token = (
                default_token_generator
                .make_token(user)
            )

            uid = urlsafe_base64_encode(
                force_bytes(user.pk)
            )

            reset_url = (
                "http://127.0.0.1:8000/"
                f"password-reset-confirm/{uid}/{token}/"
            )

            send_mail(
                subject=(
                    "CardioCare - "
                    "Password Reset Requested"
                ),
                message=(
                    f"Hello {user.username},\n\n"
                    "Click the link below to reset "
                    "your password:\n"
                    f"{reset_url}\n\n"
                    "If you did not request this, "
                    "ignore this email."
                ),
                from_email=None,
                recipient_list=[email],
                fail_silently=False,
            )

    # Do not reveal whether the email exists.
    return Response(
        {
            "message": (
                "If the email exists, password reset "
                "instructions have been sent."
            )
        },
        status=status.HTTP_200_OK,
    )


# =========================================================
# API - CARDIO PREDICTION
# =========================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_predict_cardio(request):
    serializer = CardioPredictionSerializer(
        data=request.data
    )

    if serializer.is_valid():
        data = serializer.validated_data

        bmi, risk_percentage, result_category = (
            calculate_cardio_risk(
                data["age"],
                data["gender"],
                data["weight"],
                data["height"],
                data["ap_hi"],
                data["ap_lo"],
                data["cholesterol"],
                data["gluc"],
                data["smoke"],
                data["alco"],
                data["active"],
            )
        )

        record = serializer.save(
            user=request.user,
            bmi=bmi,
            prediction_category=result_category,
            risk_percentage=risk_percentage,
        )

        return Response(
            {
                "id": record.id,
                "user": request.user.username,
                "bmi": bmi,
                "prediction_category": result_category,
                "risk_percentage": risk_percentage,
                "disclaimer": (
                    "This application is a home-based "
                    "preliminary risk screening tool "
                    "and does not constitute a "
                    "medical diagnosis."
                ),
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST,
    )


# =========================================================
# API - USER HISTORY
# =========================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_prediction_history(request):
    records = CardioPrediction.objects.filter(
        user=request.user
    ).order_by(
        "-created_at"
    )

    serializer = CardioPredictionSerializer(
        records,
        many=True,
    )

    return Response(
        serializer.data,
        status=status.HTTP_200_OK,
    )