"""Utility helpers for the health tracking application."""

import os
from datetime import date, timedelta
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'heic'}


def allowed_file(filename):
    """Check if file extension is allowed for upload."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file, upload_folder, prefix=""):
    """Save an uploaded file and return the path."""
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        return None

    filename = secure_filename(file.filename)
    if prefix:
        filename = f"{prefix}_{filename}"

    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)
    return filepath


def get_week_bounds(target_date=None):
    """Get Monday and Sunday of the week containing the given date."""
    target = target_date or date.today()
    monday = target - timedelta(days=target.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def format_nutrient_value(value, unit):
    """Format a nutrient value with appropriate precision."""
    if value is None:
        return "N/A"
    if unit in ("kcal", "mg", "ml"):
        return f"{round(value)}{unit}"
    if unit in ("g", "mcg"):
        return f"{round(value, 1)}{unit}"
    return f"{value}{unit}"
