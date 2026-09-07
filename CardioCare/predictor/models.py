from django.db import models


class CardioPrediction(models.Model):
  age = models.IntegerField()
  gender = models.IntegerField(choices=[(2, 'Male'), (1, 'Female')])
  weight = models.FloatField()
  height = models.FloatField()
  bmi = models.FloatField()
  ap_hi = models.FloatField(verbose_name='Systolic BP')
  ap_lo = models.FloatField(verbose_name='Diastolic BP')
  cholesterol = models.IntegerField(
      choices=[(1, 'Normal'), (2, 'Above Normal'), (3, 'Well Above Normal')]
  )
  gluc = models.IntegerField(
      choices=[(1, 'Normal'), (2, 'Above Normal'), (3, 'Well Above Normal')]
  )
  smoke = models.IntegerField(choices=[(0, 'No'), (1, 'Yes')])
  alco = models.IntegerField(choices=[(0, 'No'), (1, 'Yes')])
  active = models.IntegerField(choices=[(0, 'No'), (1, 'Yes')])

  prediction_category = models.CharField(max_length=50)
  risk_percentage = models.FloatField()
  created_at = models.DateTimeField(auto_now_add=True)

  def __str__(self):
    return f'{self.prediction_category} ({self.risk_percentage}%)'