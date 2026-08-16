from django.db import models
from django.contrib.auth.models import User
from competitions.models import Competition, Round


class Judge(models.Model):
    class Meta:
        db_table = 'competition_app_judge'

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20)
    profile_image = models.ImageField(
        upload_to='judge_profiles/',
        default='defaults/people.svg',
        null=True,
        blank=True
    )
    expertise = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive')
    ], default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()}"

    def get_profile_image_url(self):
        if self.profile_image:
            return self.profile_image.url
        return 'defaults/people.svg'


User.is_judge = property(lambda u: hasattr(u, 'judge'))


class JudgeAssignment(models.Model):
    class Meta:
        db_table = 'competition_app_judgeassignment'
        unique_together = ['judge', 'competition']

    judge = models.ForeignKey(Judge, on_delete=models.CASCADE, related_name='assignments')
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='judge_assignments')
    rounds = models.ManyToManyField(Round, related_name='judge_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive')
    ], default='ACTIVE')

    def __str__(self):
        return f"{self.judge} - {self.competition}"
