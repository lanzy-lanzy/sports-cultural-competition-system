import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def assign_participant_ids(apps, schema_editor):
    Participant = apps.get_model('participants', 'Participant')
    for participant in Participant.objects.filter(participant_id__isnull=True).iterator():
        participant.participant_id = f'JHCSC-{uuid.uuid4().hex[:10].upper()}'
        participant.save(update_fields=['participant_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('participants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='user',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='participant_profile',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='participant',
            name='participant_id',
            field=models.CharField(editable=False, max_length=20, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='participant',
            name='birth_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='participant',
            name='category',
            field=models.CharField(
                choices=[('JUNIOR', 'Junior'), ('OPEN', 'Open'), ('SENIOR', 'Senior / Masters')],
                default='OPEN',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='participant',
            name='team_name',
            field=models.CharField(blank=True, max_length=150, verbose_name='Team / delegation'),
        ),
        migrations.AddField(
            model_name='participant',
            name='identification_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('SCHOOL_ID', 'School ID'),
                    ('GOVERNMENT_ID', 'Government-issued ID'),
                    ('BIRTH_CERTIFICATE', 'Birth certificate'),
                    ('OTHER', 'Other identification'),
                ],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='participant',
            name='identification_number',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='participant',
            name='identification_document',
            field=models.FileField(blank=True, null=True, upload_to='participant_documents/%Y/%m/'),
        ),
        migrations.RunPython(assign_participant_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='participant',
            name='participant_id',
            field=models.CharField(editable=False, max_length=20, unique=True),
        ),
    ]
