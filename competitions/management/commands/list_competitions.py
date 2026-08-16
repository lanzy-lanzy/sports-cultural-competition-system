from django.core.management.base import BaseCommand
from competitions.models import Competition

class Command(BaseCommand):
    help = 'Lists all competitions in the database'

    def handle(self, *args, **kwargs):
        competitions = Competition.objects.all()
        self.stdout.write('Listing all competitions:')
        for comp in competitions:
            self.stdout.write(f'ID: {comp.id}, Name: {comp.name}, Status: {comp.status}, Show Results: {comp.show_results}')
