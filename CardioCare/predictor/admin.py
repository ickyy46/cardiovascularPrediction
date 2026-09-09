from django.contrib import admin

from .models import CardioPrediction


@admin.register(CardioPrediction)
class CardioPredictionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "age", "gender", "bmi", "prediction_category",
        "risk_percentage", "created_at",
    )
    list_filter = ("prediction_category", "gender", "cholesterol", "gluc", "created_at")
    search_fields = ("user__username", "user__email", "prediction_category")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


admin.site.site_header = "CardioCare Administration"
admin.site.site_title = "CardioCare Admin"
admin.site.index_title = "System Administration"
