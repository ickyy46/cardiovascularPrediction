from rest_framework import serializers
from .models import CardioPrediction


class CardioPredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CardioPrediction
        fields = "__all__"
        read_only_fields = (
            "id",
            "user",
            "bmi",
            "prediction_category",
            "risk_percentage",
            "created_at",
        )
