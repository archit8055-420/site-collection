from django.db import models
from django.utils import timezone

class AppUser(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    default_report_title = models.CharField(max_length=255, default="Veraval site daily progress report")

class SavedArea(models.Model):
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="areas")
    area_name = models.CharField(max_length=150)
    class Meta:
        unique_together = ("user", "area_name")

class SavedLabour(models.Model):
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="labours")
    labour_name = models.CharField(max_length=150)
    class Meta:
        unique_together = ("user", "labour_name")

class DailyReport(models.Model):
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="reports")
    report_title = models.CharField(max_length=255)
    report_date = models.DateField(default=timezone.now)
    area_name = models.CharField(max_length=150, blank=True, default="")
    labour_name = models.CharField(max_length=150, blank=True, default="")
    qty_63mm = models.FloatField(default=0)
    qty_90mm = models.FloatField(default=0)
    qty_110mm = models.FloatField(default=0)
    qty_150mm = models.FloatField(default=0)
    total_pvc = models.FloatField(default=0)
    total_di = models.FloatField(default=0)
    total_qty = models.FloatField(default=0)
    price_sum = models.FloatField(default=0.0)

class PasswordResetToken(models.Model):
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
