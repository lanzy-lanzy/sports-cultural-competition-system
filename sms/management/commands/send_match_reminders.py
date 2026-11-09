from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from sms.models import SmsMessage
from sms.services import describe_summary, is_configured, notify_match
from sports.models import Match


class Command(BaseCommand):
    help = (
        'Text contestants and team staff a reminder for matches starting within '
        'the next few hours. Safe to run from a scheduler (for example every hour).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='How far ahead to look for matches (default: 24).',
        )
        parser.add_argument(
            '--competition',
            type=int,
            help='Only remind matches in this competition id.',
        )
        parser.add_argument(
            '--include-players',
            action='store_true',
            help='Also text every active player on a team roster.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Send again even when a reminder was already sent for this schedule.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List the matches that would be reminded without sending SMS.',
        )

    def handle(self, *args, **options):
        now = timezone.now()
        window_end = now + timedelta(hours=max(options['hours'], 1))
        matches = (
            Match.objects
            .filter(
                status=Match.Status.SCHEDULED,
                scheduled_start__gte=now,
                scheduled_start__lte=window_end,
            )
            .select_related('event', 'event__competition', 'venue')
            .prefetch_related('entries__team', 'entries__participant')
            .order_by('scheduled_start', 'id')
        )
        if options['competition']:
            matches = matches.filter(event__competition_id=options['competition'])

        if not is_configured():
            self.stdout.write(self.style.WARNING(
                'SMS is not configured. Add SEMAPHORE_API_KEY and '
                'SEMAPHORE_SENDER_NAME to .env first.'
            ))

        sent = skipped = 0
        for match in matches:
            if not match.entries.exists():
                continue
            if not options['force']:
                already_sent = SmsMessage.objects.filter(
                    match=match,
                    category=SmsMessage.Category.REMINDER,
                    status=SmsMessage.Status.SENT,
                    created_at__gte=match.updated_at,
                ).exists()
                if already_sent:
                    skipped += 1
                    continue

            label = f'{match.event.name} - {match.label} ({match.contestants_display()})'
            when = timezone.localtime(match.scheduled_start).strftime('%b %d %H:%M')
            if options['dry_run']:
                self.stdout.write(f'Would remind: {label} at {when}')
                sent += 1
                continue

            summary = notify_match(
                match,
                'reminder',
                include_team_players=options['include_players'] or None,
            )
            if summary['sent']:
                sent += 1
                self.stdout.write(self.style.SUCCESS(
                    f'{label} at {when}: {describe_summary(summary)}'
                ))
            elif summary['failed']:
                self.stdout.write(self.style.ERROR(
                    f'{label} at {when}: {describe_summary(summary)}'
                ))
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f'{label} at {when}: {describe_summary(summary)}'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'Done. {sent} match reminder(s) processed, {skipped} skipped.'
        ))
