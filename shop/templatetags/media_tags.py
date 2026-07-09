# shop/templatetags/media_tags.py
import re
from django import template

register = template.Library()

@register.filter
def youtube_id(value):
    """Extracts the 11-char YouTube video ID from any common URL format."""
    if not value:
        return ''
    # Already a bare 11-char ID
    if re.fullmatch(r'[\w-]{11}', value):
        return value
    match = re.search(r'(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|v/))([\w-]{11})', value)
    return match.group(1) if match else ''