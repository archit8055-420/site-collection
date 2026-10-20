import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AppUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=150)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('password', models.CharField(max_length=255)),
                ('default_report_title', models.CharField(default='Veraval site daily progress report', max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='SavedArea',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('area_name', models.CharField(max_length=150)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='areas', to='models_app.appuser')),
            ],
            options={
                'unique_together': {('user', 'area_name')},
            },
        ),
        migrations.CreateModel(
            name='SavedLabour',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('labour_name', models.CharField(max_length=150)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='labours', to='models_app.appuser')),
            ],
            options={
                'unique_together': {('user', 'labour_name')},
            },
        ),
        migrations.CreateModel(
            name='DailyReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_title', models.CharField(max_length=255)),
                ('report_date', models.DateField(default=django.utils.timezone.now)),
                ('area_name', models.CharField(blank=True, default='', max_length=150)),
                ('labour_name', models.CharField(blank=True, default='', max_length=150)),
                ('qty_63mm', models.FloatField(default=0)),
                ('qty_90mm', models.FloatField(default=0)),
                ('qty_110mm', models.FloatField(default=0)),
                ('qty_150mm', models.FloatField(default=0)),
                ('extra_63mm', models.FloatField(default=0)),
                ('extra_90mm', models.FloatField(default=0)),
                ('extra_110mm', models.FloatField(default=0)),
                ('extra_150mm', models.FloatField(default=0)),
                ('total_pvc', models.FloatField(default=0)),
                ('total_di', models.FloatField(default=0)),
                ('total_qty', models.FloatField(default=0)),
                ('total_mtr', models.FloatField(default=0)),
                ('price_sum', models.FloatField(default=0.0)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='models_app.appuser')),
            ],
        ),
        migrations.CreateModel(
            name='PasswordResetToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=100, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='models_app.appuser')),
            ],
        ),
    ]
