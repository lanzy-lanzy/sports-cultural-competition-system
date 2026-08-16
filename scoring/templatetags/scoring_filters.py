from django import template

register = template.Library()


@register.filter
def elided_pages(page_obj, on_each_side=2, on_ends=1):
    ellipsis = page_obj.paginator.ELLIPSIS
    return [
        str(num) if num == ellipsis else num
        for num in page_obj.paginator.get_elided_page_range(
            page_obj.number,
            on_each_side=on_each_side,
            on_ends=on_ends,
        )
    ]


@register.filter
def get_score(score_lookup, ids):
    """Gets score from lookup dictionary using participant and criterion IDs"""
    participant_id, criterion_id = ids.split(',')
    return score_lookup.get((int(participant_id), int(criterion_id)), '')


@register.filter
def get_remarks(score_lookup, key_pair):
    """Get remarks value from lookup dictionary"""
    participant_id, criterion_id = key_pair
    key = f"{participant_id}_{criterion_id}"
    score = score_lookup.get(key)
    return score.remarks if score else ''


@register.filter(name='get_item')
def get_item(dictionary, key):
    """Get item from dictionary with nested lookup support"""
    if dictionary is None:
        return None
    if isinstance(dictionary, dict):
        return dictionary.get(key, {})
    return None
