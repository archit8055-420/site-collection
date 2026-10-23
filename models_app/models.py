from django.db import models

class AppUser(models.Model):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    default_report_title = models.CharField(max_length=255, default="Veraval site daily progress report")
    default_area_name = models.CharField(max_length=255, default="", blank=True)
    default_labour_name = models.CharField(max_length=255, default="", blank=True)
    default_connection = models.CharField(max_length=100, default="", blank=True)
    # Per pipe MTR - permanent
    mtr_63mm = models.FloatField(default=6.0)
    mtr_90mm = models.FloatField(default=6.0)
    mtr_110mm = models.FloatField(default=6.0)
    mtr_150mm = models.FloatField(default=5.5)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return self.username

class SavedArea(models.Model):
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name='areas')
    area_name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        unique_together = ('user', 'area_name')

    def __str__(self):
        return self.area_name

class SavedLabour(models.Model):
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name='labours')
    labour_name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        unique_together = ('user', 'labour_name')

    def __str__(self):
        return self.labour_name

class DailyReport(models.Model):
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name='reports', null=True)
    report_title = models.CharField(max_length=255, default="Site Daily Progress Report")
    report_date = models.DateField()
    area_name = models.CharField(max_length=150)
    labour_name = models.CharField(max_length=150, default="", blank=True)
    connection = models.CharField(max_length=100, default="", blank=True)
    qty_63mm = models.FloatField(default=0)
    qty_90mm = models.FloatField(default=0)
    qty_110mm = models.FloatField(default=0)
    qty_150mm = models.FloatField(default=0)
    extra_63mm = models.FloatField(default=0)
    extra_90mm = models.FloatField(default=0)
    extra_110mm = models.FloatField(default=0)
    extra_150mm = models.FloatField(default=0)
    total_mtr = models.FloatField(default=0)
    count_63mm = models.IntegerField(default=0)
    count_90mm = models.IntegerField(default=0)
    count_110mm = models.IntegerField(default=0)
    count_150mm = models.IntegerField(default=0)
    total_pvc = models.FloatField(default=0)
    total_di = models.FloatField(default=0)
    total_qty = models.FloatField(default=0)
    price_sum = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.area_name} - {self.report_date}"

class ConnectionEntry(models.Model):
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name='connections', null=True)
    report = models.ForeignKey(DailyReport, on_delete=models.CASCADE, related_name='connection_entries', null=True, blank=True)
    report_date = models.DateField()
    connection_no = models.CharField(max_length=100, default="", blank=True)
    name = models.CharField(max_length=150, default="", blank=True)
    mobile = models.CharField(max_length=20, default="", blank=True)
    area_name = models.CharField(max_length=100, default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.connection_no},{self.name},{self.mobile} - {self.report_date}"

class PasswordResetToken(models.Model):
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reset token for {self.user.email}"
