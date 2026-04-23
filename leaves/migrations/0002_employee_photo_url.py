from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='photo_url',
            field=models.URLField(blank=True),
        ),
    ]
