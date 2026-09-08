from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import CardioPrediction


VALID_FORM = {
    "age": "45",
    "gender": "2",
    "weight": "72",
    "height": "175",
    "ap_hi": "120",
    "ap_lo": "80",
    "cholesterol": "1",
    "gluc": "1",
    "smoke": "0",
    "alco": "0",
    "active": "1",
    "genetic": "0",
}


class AssessmentFlowTests(TestCase):
    @patch("predictor.views.calculate_cardio_risk", return_value=(23.51, 18.5, "Lower Predicted Likelihood"))
    def test_anonymous_result_is_not_saved(self, _mock):
        response = self.client.post(reverse("predict_cardio"), VALID_FORM)
        self.assertRedirects(response, reverse("anonymous_result"))
        self.assertEqual(CardioPrediction.objects.count(), 0)
        result = self.client.get(reverse("anonymous_result"))
        self.assertContains(result, "18.5%")
        self.assertContains(result, "has not been saved")

    @patch("predictor.views.calculate_cardio_risk", return_value=(23.51, 18.5, "Lower Predicted Likelihood"))
    def test_logged_in_result_is_saved_to_own_history(self, _mock):
        user = User.objects.create_user(username="tester", password="strong-pass-123")
        self.client.login(username="tester", password="strong-pass-123")
        response = self.client.post(reverse("predict_cardio"), VALID_FORM)
        record = CardioPrediction.objects.get()
        self.assertEqual(record.user, user)
        self.assertRedirects(response, reverse("result_detail", args=[record.pk]))
        history = self.client.get(reverse("prediction_history"))
        self.assertContains(history, "Lower Predicted Likelihood")

    def test_history_requires_login(self):
        response = self.client.get(reverse("prediction_history"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
