from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("predictor", "0002_cardio_prediction_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="cardioprediction",
            name="genetic",
            field=models.IntegerField(
                choices=[(0, "No"), (1, "Yes")],
                default=0,
            ),
        ),
    ]
