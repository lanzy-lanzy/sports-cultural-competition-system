from django import template
from participants.models import Participant

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def get_participant(competition, participant_id):
    return competition.participants.filter(id=participant_id).first()


@register.filter
def format_score(value):
    if value is None:
        return "-"
    return "{:.2f}".format(float(value))


@register.filter
def average(value_list):
    """Calculate the average of a list of values"""
    try:
        values = [float(v) for v in value_list if v is not None]
        if not values:
            return 0
        return sum(values) / len(values)
    except (TypeError, ValueError):
        return 0
