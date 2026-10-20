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

class DailyReport(models.Model):
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="reports")
    report_title = models.CharField(max_length=255)
    report_date = models.DateField(default=timezone.now)
    area_name = models.CharField(max_length=150, blank=True, default="")
    qty_63mm = models.IntegerField(default=0)
    qty_90mm = models.IntegerField(default=0)
    qty_110mm = models.IntegerField(default=0)
    qty_150mm = models.IntegerField(default=0)  # NEW - 150MM DI - Same as 63MM
    total_pvc = models.IntegerField(default=0)  # NEW - PVC total 63+90+110
    total_di = models.IntegerField(default=0)   # NEW - DI total
    total_qty = models.IntegerField(default=0)
    price_sum = models.FloatField(default=0.0)

class PasswordResetToken(models.Model):
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
