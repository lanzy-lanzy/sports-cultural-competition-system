from decimal import Decimal

from django.db import models
from django.db.models import Count
from django.contrib.auth.models import User


class Competition(models.Model):
    class Kind(models.TextChoices):
        SPORTS = 'SPORTS', 'Sports competition'
        CULTURAL = 'CULTURAL', 'Cultural competition'
        MIXED = 'MIXED', 'Mixed / other'

    class TournamentFormat(models.TextChoices):
        SINGLE_ELIMINATION = 'SINGLE_ELIMINATION', 'Single Elimination'
        DOUBLE_ELIMINATION = 'DOUBLE_ELIMINATION', 'Double Elimination'
        ROUND_ROBIN = 'ROUND_ROBIN', 'Round Robin'
        GROUP_KNOCKOUT = 'GROUP_KNOCKOUT', 'Group Stage + Knockout'
        BEST_OF = 'BEST_OF', 'Best-of Series'
        LEAGUE = 'LEAGUE', 'League Format'

    tournament_format = models.CharField(
        max_length=20, choices=TournamentFormat.choices, blank=True, default='',
    )

    class CulturalEventType(models.TextChoices):
        DANCE = 'DANCE', 'Dance Competition'
        SINGING = 'SINGING', 'Singing Competition'
        CULTURAL_PRESENTATION = 'CULTURAL_PRESENTATION', 'Cultural Presentation'
        ESSAY_WRITING = 'ESSAY_WRITING', 'Essay Writing'
        POSTER_MAKING = 'POSTER_MAKING', 'Poster Making'
        QUIZ_BEE = 'QUIZ_BEE', 'Quiz Bee'
        SPOKEN_POETRY = 'SPOKEN_POETRY', 'Spoken Poetry'
        COSTUME = 'COSTUME', 'Costume Competition'
        TALENT_SHOW = 'TALENT_SHOW', 'Talent Show'
        OTHER = 'OTHER', 'Other cultural event'

    class Meta:
        db_table = 'competition_app_competition'

    name = models.CharField(max_length=200)
    description = models.TextField()
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.MIXED,
        help_text='What kind of competition this is.',
    )
    cultural_event_type = models.CharField(
        max_length=30,
        blank=True,
        default='',
        help_text='Only used for cultural competitions. Stores a CulturalSubType slug.',
    )
    gold_points = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10'),
        help_text='Points per gold medal in the medal tally.',
    )
    silver_points = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('5'),
        help_text='Points per silver medal in the medal tally.',
    )
    bronze_points = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('3'),
        help_text='Points per bronze medal in the medal tally.',
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=[
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled')
    ], default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='competitions_created')
    show_results = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    @property
    def uses_judging(self):
        return self.kind != self.Kind.SPORTS

    def get_cultural_event_type_display(self):
        return cultural_subtype_labels().get(
            self.cultural_event_type, self.cultural_event_type
        )


class CulturalMainType(models.Model):
    """Main group a cultural sub-type belongs to (e.g. Performing Arts)."""

    class Meta:
        db_table = 'competition_app_cultural_main_type'
        ordering = ['id']

    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class CulturalSubType(models.Model):
    """Selectable cultural sub-type; its slug is stored on Competition.cultural_event_type."""

    class Meta:
        db_table = 'competition_app_cultural_sub_type'
        ordering = ['id']

    main_type = models.ForeignKey(CulturalMainType, on_delete=models.CASCADE, related_name='subtypes')
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=30, unique=True)

    def __str__(self):
        return self.name


STATIC_CULTURAL_CATALOG = (
    ('VISUAL ARTS', (
        ('ON_THE_SPOT_POSTER_MAKING', 'On the Spot Poster Making'),
        ('PENCIL_DRAWING', 'Pencil Drawing'),
        ('CHARCOAL_RENDERING', 'Charcoal Rendering'),
        ('PAINTING', 'Painting'),
        ('PHOTO_CONTEST', 'Photo Contest'),
    )),
    ('MUSIC', (
        ('SONGWRITING', 'Songwriting'),
        ('PIANO', 'Piano'),
        ('VIOLIN', 'Violin'),
        ('CLASSICAL_GUITAR', 'Classical Guitar'),
        ('BANDURIA', 'Banduria'),
        ('LIVE_BAND_COMPETITION', 'Live Band Competition'),
        ('VOCAL_SOLO_KUNDIMAN', 'Vocal Solo (Kundiman)'),
        ('VOCAL_DUET', 'Vocal Duet'),
        ('POP_SOLO_QUARTET', 'Pop Solo Quartet'),
        ('STANDARD_CHORALE_CONTEST', 'Standard Chorale Contest'),
        ('SHOW_CHOIR', 'Show Choir'),
    )),
    ('DANCE', (
        ('FOLK_DANCE', 'Folk Dance'),
        ('INDIGENOUS_DANCE', 'Indigenous Dance'),
        ('CONTEMPORARY_DUO', 'Contemporary Duo'),
        ('CONTEMPORARY_DANCE', 'Contemporary Dance'),
        ('STREET_DANCE', 'Street Dance'),
        ('MASS_POWER_DANCE', 'Mass Power Dance'),
        ('LATIN_AMERICAN_DANCE', 'Latin American Dance'),
        ('MODERN_STANDARD_DANCE', 'Modern Standard Dance'),
    )),
    ('DRAMATIC ARTS', (
        ('SHORT_SWEET_PLAYS_DIALOGUE', 'Short and Sweet Plays (Dialogue)'),
        ('SHORT_SWEET_PLAY_MUSICAL', 'Short and Sweet Play (Musical)'),
        ('RADIO_DRAMA', 'Radio Drama'),
        ('DUO_ACTING', 'Duo Acting'),
        ('PANDALAWAHANG_PAG_ARTE', 'Pandalawahang Pag-arte (Duo Acting)'),
    )),
    ('LITERARY ARTS', (
        ('PAGSULAT_NG_SANAYSAY', 'Pagsulat ng Sanaysay'),
        ('DAGLIANG_TALUMPATI', 'Dagliang Talumpati'),
        ('PAGKUKUWENTO', 'Pagkukuwento'),
        ('ESSAY_WRITING', 'Essay Writing'),
        ('EXTEMPORANEOUS_SPEECH', 'Extemporaneous Speech'),
        ('STORY_TELLING', 'Story Telling'),
        ('DECLAMATION', 'Declamation'),
        ('DEKLAMASYON', 'Deklamasyon'),
        ('DRAMATIC_MONOLOGUE', 'Dramatic Monologue'),
        ('DRAMATIC_MONOLOGUE_FILIPINO', 'Dramatic Monologue (Filipino)'),
        ('ORAL_INTERPRETATION_POETRY', 'Oral Interpretation of Poetry'),
        ('PERSUASIVE_ORATORY', 'Persuasive Oratory'),
        ('ORATORIO', 'Oratorio'),
    )),
    ('SPECIAL CATEGORY', (
        ('MR_PAGEANT', 'Mr.'),
        ('MS_PAGEANT', 'Ms.'),
        ('FESTIVAL_DANCE_COMPETITION', 'Festival Dance Competition'),
    )),
)

STATIC_CULTURAL_LABELS = {
    slug: name
    for _main, items in STATIC_CULTURAL_CATALOG
    for slug, name in items
}


def ensure_static_cultural_catalog():
    """Ensure all static Socio Cultural main groups and sub-types exist in the DB."""
    existing_mains = {m.name: m for m in CulturalMainType.objects.all()}
    existing_slugs = set(CulturalSubType.objects.values_list('slug', flat=True))
    for main_name, items in STATIC_CULTURAL_CATALOG:
        main = existing_mains.get(main_name)
        if main is None:
            main, _ = CulturalMainType.objects.get_or_create(name=main_name)
            existing_mains[main_name] = main
        for slug, sub_name in items:
            if slug not in existing_slugs:
                CulturalSubType.objects.get_or_create(
                    slug=slug,
                    defaults={'main_type': main, 'name': sub_name},
                )
                existing_slugs.add(slug)


def cultural_subtype_labels():
    """Slug -> display name; includes static catalog and legacy enum fallbacks."""
    labels = dict(Competition.CulturalEventType.choices)
    labels.update(STATIC_CULTURAL_LABELS)
    labels.update(CulturalSubType.objects.values_list('slug', 'name'))
    return labels


def cultural_subtype_groups():
    """Static main groups with their sub-types (plus any custom DB groups),
    for the Socio Cultural event dropdown."""
    ensure_static_cultural_catalog()
    usage = dict(
        Competition.objects
        .exclude(cultural_event_type='')
        .values_list('cultural_event_type')
        .annotate(n=Count('id'))
    )
    static_main_names = [main_name for main_name, _ in STATIC_CULTURAL_CATALOG]
    static_order = {name: idx for idx, name in enumerate(static_main_names)}
    mains = list(CulturalMainType.objects.prefetch_related('subtypes'))
    mains.sort(key=lambda m: (0, static_order[m.name]) if m.name in static_order else (1, m.id))

    groups = []
    for main in mains:
        if main.name in static_order:
            static_slugs = [slug for slug, _ in dict(STATIC_CULTURAL_CATALOG)[main.name]]
            slug_order = {s: i for i, s in enumerate(static_slugs)}
            subs = sorted(
                main.subtypes.all(),
                key=lambda s: (0, slug_order[s.slug]) if s.slug in slug_order else (1, s.name.lower()),
            )
        else:
            subs = list(main.subtypes.all())
        if not subs:
            continue
        groups.append({
            'id': main.id,
            'name': main.name,
            'subtypes': [
                {'id': sub.id, 'slug': sub.slug, 'name': sub.name, 'usage': usage.get(sub.slug, 0)}
                for sub in subs
            ],
        })
    return groups


class Round(models.Model):
    class Meta:
        db_table = 'competition_app_round'
        ordering = ['order']

    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='rounds')
    name = models.CharField(max_length=200)
    description = models.TextField()
    order = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed')
    ], default='PENDING')
    weight_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    def __str__(self):
        return self.name


class Criterion(models.Model):
    class Meta:
        db_table = 'competition_app_criterion'

    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='criteria')
    name = models.CharField(max_length=200)
    description = models.TextField()
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    weight_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text=(
            'Optional percentage weight (e.g. 30 for 30%). When any criterion in '
            'the round uses weights, totals are computed as the weighted sum of '
            'criterion scores; otherwise criterion averages are summed directly.'
        ),
    )

    def __str__(self):
        return self.name
