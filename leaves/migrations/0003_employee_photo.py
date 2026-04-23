from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0002_employee_photo_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='photo',
            field=models.ImageField(blank=True, upload_to='employee_photos/'),
        ),
    ]
