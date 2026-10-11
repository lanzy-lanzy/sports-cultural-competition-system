from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('participants', '0002_participant_identity_and_documents'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(editable=False, max_length=20, unique=True)),
                ('name', models.CharField(max_length=150, unique=True)),
                ('category', models.CharField(choices=[('SPORTS', 'Sports Team'), ('CULTURAL', 'Cultural Delegation'), ('MIXED', 'Mixed Delegation')], max_length=20)),
                ('description', models.TextField(blank=True)),
                ('logo', models.ImageField(blank=True, null=True, upload_to='team_logos/')),
                ('status', models.CharField(choices=[('PENDING', 'Pending approval'), ('APPROVED', 'Approved'), ('SUSPENDED', 'Suspended')], default='PENDING', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_competition_teams', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='TeamStaff',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('COACH', 'Coach'), ('MANAGER', 'Team Manager')], max_length=20)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='staff_assignments', to='teams.team')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='team_staff_assignments', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['role', 'user__last_name', 'user__first_name']},
        ),
        migrations.CreateModel(
            name='TeamMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('member_number', models.PositiveIntegerField(blank=True, null=True)),
                ('status', models.CharField(choices=[('ACTIVE', 'Active'), ('INACTIVE', 'Inactive')], default='ACTIVE', max_length=20)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('participant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='team_membership', to='participants.participant')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='teams.team')),
            ],
            options={'ordering': ['member_number', 'participant__name']},
        ),
        migrations.AddField(
            model_name='team',
            name='members',
            field=models.ManyToManyField(related_name='teams', through='teams.TeamMembership', to='participants.participant'),
        ),
        migrations.AddField(
            model_name='team',
            name='staff',
            field=models.ManyToManyField(related_name='competition_teams', through='teams.TeamStaff', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddConstraint(
            model_name='teamstaff',
            constraint=models.UniqueConstraint(fields=('team', 'user', 'role'), name='unique_team_staff_role'),
        ),
        migrations.AddConstraint(
            model_name='teammembership',
            constraint=models.UniqueConstraint(fields=('team', 'member_number'), name='unique_team_member_number'),
        ),
    ]
