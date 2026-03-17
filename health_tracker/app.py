"""Main Flask application for the Health Tracker."""

import os
from datetime import date, datetime
from flask import (Flask, render_template, request, jsonify, redirect,
                   url_for, flash, session)
from flask_cors import CORS
from models.database import db, User, FoodEntry, FitnessData, BodyMetric, SymptomEntry
from services.food_service import FoodService
from services.nutrient_service import NutrientService
from services.fitness_service import FitnessService
from services.allowance_service import AllowanceService
from services.symptom_service import SymptomService
from utils.helpers import save_upload


def create_app(config=None):
    """Application factory."""
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'sqlite:///health_tracker.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    if config:
        app.config.update(config)

    # Initialize extensions
    db.init_app(app)
    CORS(app)

    # Initialize services
    food_service = FoodService()
    nutrient_service = NutrientService()
    fitness_service = FitnessService()
    allowance_service = AllowanceService()
    symptom_service = SymptomService()

    # Create tables
    with app.app_context():
        db.create_all()

    # ── Page Routes ──────────────────────────────────────────────────

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html')

    @app.route('/food')
    def food_page():
        return render_template('food.html')

    @app.route('/symptoms')
    def symptoms_page():
        return render_template('symptoms.html')

    @app.route('/settings')
    def settings_page():
        return render_template('settings.html')

    # ── User API ─────────────────────────────────────────────────────

    @app.route('/api/user/setup', methods=['POST'])
    def setup_user():
        """Create or update user profile."""
        data = request.json
        user = User.query.first()  # Single-user app for now

        if not user:
            user = User(
                username=data.get('username', 'user'),
                email=data.get('email', 'user@example.com'),
                password_hash='not-implemented',
            )
            db.session.add(user)

        for field in ['age', 'weight_kg', 'height_cm', 'gender', 'activity_level',
                       'goal_type', 'target_weight_kg', 'daily_calorie_target',
                       'daily_protein_g', 'daily_carbs_g', 'daily_fat_g',
                       'daily_fiber_g', 'daily_water_ml', 'weekly_alcohol_units',
                       'weekly_cheat_meals', 'weekly_rest_days']:
            if field in data:
                setattr(user, field, data[field])

        db.session.commit()
        return jsonify({"status": "ok", "user_id": user.id})

    @app.route('/api/user/profile')
    def get_profile():
        """Get user profile."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "No profile configured"}), 404
        return jsonify({
            "id": user.id, "username": user.username,
            "age": user.age, "weight_kg": user.weight_kg,
            "height_cm": user.height_cm, "gender": user.gender,
            "activity_level": user.activity_level, "goal_type": user.goal_type,
            "target_weight_kg": user.target_weight_kg,
            "daily_calorie_target": user.daily_calorie_target,
            "daily_protein_g": user.daily_protein_g,
            "daily_carbs_g": user.daily_carbs_g,
            "daily_fat_g": user.daily_fat_g,
            "bmr": user.get_bmr(), "tdee": user.get_tdee(),
            "weekly_alcohol_units": user.weekly_alcohol_units,
            "weekly_cheat_meals": user.weekly_cheat_meals,
        })

    # ── Food & Drink API ─────────────────────────────────────────────

    @app.route('/api/food/search')
    def search_food():
        """Search the food database."""
        query = request.args.get('q', '')
        results = food_service.search_food(query)
        return jsonify(results)

    @app.route('/api/food/log', methods=['POST'])
    def log_food():
        """Log a food or drink entry."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400

        # Handle both JSON and form data (for image uploads)
        if request.content_type and 'multipart/form-data' in request.content_type:
            name = request.form.get('name')
            meal_type = request.form.get('meal_type', 'snack')
            servings = float(request.form.get('servings', 1))
            image = request.files.get('image')
            image_path = save_upload(image, app.config['UPLOAD_FOLDER'],
                                     prefix="food") if image else None

            # Check for custom nutrients
            custom = {}
            for field in ['calories', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g']:
                val = request.form.get(field)
                if val:
                    custom[field] = float(val)

            if custom:
                entry = food_service.log_custom_food(
                    user.id, name, meal_type, custom, servings, image_path)
            else:
                entry = food_service.log_food(
                    user.id, name, meal_type, servings, image_path)
        else:
            data = request.json
            name = data.get('name')
            meal_type = data.get('meal_type', 'snack')
            servings = float(data.get('servings', 1))
            custom = data.get('custom_nutrients')

            if custom:
                entry = food_service.log_custom_food(
                    user.id, name, meal_type, custom, servings)
            else:
                entry = food_service.log_food(
                    user.id, name, meal_type, servings)

        return jsonify(entry.to_dict())

    @app.route('/api/food/upload-image', methods=['POST'])
    def upload_food_image():
        """Upload a food image for analysis."""
        image = request.files.get('image')
        if not image:
            return jsonify({"error": "No image provided"}), 400

        image_path = save_upload(image, app.config['UPLOAD_FOLDER'], prefix="food")
        analysis = food_service.analyze_image(image_path)
        analysis['image_path'] = image_path
        return jsonify(analysis)

    @app.route('/api/food/daily')
    def daily_food():
        """Get daily food summary."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400
        target = request.args.get('date')
        target_date = date.fromisoformat(target) if target else None
        return jsonify(food_service.get_daily_summary(user.id, target_date))

    @app.route('/api/food/<int:entry_id>', methods=['DELETE'])
    def delete_food(entry_id):
        """Delete a food entry."""
        entry = FoodEntry.query.get_or_404(entry_id)
        db.session.delete(entry)
        db.session.commit()
        return jsonify({"status": "deleted"})

    # ── Nutrient Analysis API ────────────────────────────────────────

    @app.route('/api/nutrients/daily')
    def daily_nutrients():
        """Get daily nutrient analysis."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400
        target = request.args.get('date')
        target_date = date.fromisoformat(target) if target else None
        return jsonify(nutrient_service.analyze_daily(user.id, target_date))

    @app.route('/api/nutrients/weekly')
    def weekly_nutrients():
        """Get weekly nutrient analysis."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400
        weeks = int(request.args.get('weeks', 1))
        return jsonify(nutrient_service.analyze_weekly(user.id, weeks))

    # ── Fitness API ──────────────────────────────────────────────────

    @app.route('/api/fitness/daily')
    def daily_fitness():
        """Get daily fitness status."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400
        target = request.args.get('date')
        target_date = date.fromisoformat(target) if target else None
        return jsonify(fitness_service.get_daily_status(user.id, target_date))

    @app.route('/api/fitness/log', methods=['POST'])
    def log_fitness():
        """Log manual fitness data."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400

        data = request.json
        entry = FitnessData(
            user_id=user.id,
            source=data.get('source', 'manual'),
            date=date.fromisoformat(data['date']) if 'date' in data else date.today(),
        )
        for field in ['steps', 'active_calories', 'total_calories_burned',
                       'distance_km', 'exercise_minutes', 'exercise_type',
                       'resting_heart_rate', 'avg_heart_rate', 'max_heart_rate',
                       'hrv_ms', 'sleep_hours', 'sleep_quality_score',
                       'recovery_score', 'strain_score']:
            if field in data:
                setattr(entry, field, data[field])

        db.session.add(entry)
        db.session.commit()
        return jsonify(entry.to_dict())

    @app.route('/api/fitness/progress')
    def fitness_progress():
        """Get fitness progress report."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400
        days = int(request.args.get('days', 7))
        return jsonify(fitness_service.get_progress_report(user.id, days))

    # ── Body Metrics API ─────────────────────────────────────────────

    @app.route('/api/body/log', methods=['POST'])
    def log_body_metric():
        """Log body composition data."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400

        data = request.json
        entry = BodyMetric(
            user_id=user.id,
            source=data.get('source', 'manual'),
            date=date.fromisoformat(data['date']) if 'date' in data else date.today(),
        )
        for field in ['weight_kg', 'bmi', 'body_fat_pct', 'muscle_mass_kg',
                       'bone_mass_kg', 'water_pct', 'visceral_fat',
                       'basal_metabolism', 'metabolic_age', 'protein_pct']:
            if field in data:
                setattr(entry, field, data[field])

        db.session.add(entry)
        db.session.commit()
        return jsonify(entry.to_dict())

    # ── Allowance API ────────────────────────────────────────────────

    @app.route('/api/allowances')
    def get_allowances():
        """Get current weekly allowance status."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400
        return jsonify(allowance_service.get_allowance_status(user.id))

    @app.route('/api/allowances/use', methods=['POST'])
    def use_allowance():
        """Use an allowance (alcohol, cheat meal, rest day, dining out)."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400
        data = request.json
        return jsonify(allowance_service.use_allowance(
            user.id, data['type'], data.get('amount', 1)))

    # ── Symptom API ──────────────────────────────────────────────────

    @app.route('/api/symptoms/log', methods=['POST'])
    def log_symptom():
        """Log a symptom with optional image."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400

        if request.content_type and 'multipart/form-data' in request.content_type:
            symptom_type = request.form.get('symptom_type')
            description = request.form.get('description')
            severity = int(request.form.get('severity', 5))
            body_area = request.form.get('body_area')
            duration = request.form.get('duration_hours')
            image = request.files.get('image')
            image_path = save_upload(image, app.config['UPLOAD_FOLDER'],
                                     prefix="symptom") if image else None
        else:
            data = request.json
            symptom_type = data.get('symptom_type')
            description = data.get('description')
            severity = data.get('severity', 5)
            body_area = data.get('body_area')
            duration = data.get('duration_hours')
            image_path = None

        result = symptom_service.log_symptom(
            user.id, symptom_type, description, severity,
            image_path, body_area, float(duration) if duration else None)
        return jsonify(result)

    @app.route('/api/symptoms/history')
    def symptom_history():
        """Get symptom history."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400
        days = int(request.args.get('days', 30))
        return jsonify(symptom_service.get_symptom_history(user.id, days))

    @app.route('/api/symptoms/<int:symptom_id>/resolve', methods=['POST'])
    def resolve_symptom(symptom_id):
        """Mark a symptom as resolved."""
        entry = symptom_service.resolve_symptom(symptom_id)
        if entry:
            return jsonify(entry.to_dict())
        return jsonify({"error": "Symptom not found"}), 404

    # ── Sync API (external devices) ──────────────────────────────────

    @app.route('/api/sync/whoop', methods=['POST'])
    def sync_whoop():
        """Trigger Whoop data sync."""
        user = User.query.first()
        if not user or not user.whoop_access_token:
            return jsonify({"error": "Whoop not connected"}), 400

        from api.whoop_client import WhoopClient
        client = WhoopClient(access_token=user.whoop_access_token,
                             refresh_token=user.whoop_refresh_token)
        try:
            data = client.sync_daily_data()
            # Save to fitness_data
            entry = FitnessData(user_id=user.id, **{
                k: v for k, v in data.items()
                if k not in ('date', 'source') and v is not None
            })
            entry.source = 'whoop'
            entry.date = date.fromisoformat(data['date'])
            db.session.add(entry)
            db.session.commit()
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/sync/apple-health', methods=['POST'])
    def sync_apple_health():
        """Accept Apple Health data push."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400

        from api.apple_health_client import AppleHealthClient
        client = AppleHealthClient()
        data = client.process_sync_payload(request.json)

        entry = FitnessData(user_id=user.id, source='apple_health')
        entry.date = date.fromisoformat(data.get('date', date.today().isoformat()))
        for field in ['steps', 'active_calories', 'exercise_minutes',
                       'resting_heart_rate', 'hrv_ms', 'sleep_hours',
                       'distance_km', 'avg_heart_rate', 'max_heart_rate']:
            if field in data:
                setattr(entry, field, data[field])

        db.session.add(entry)

        # Also save body metrics if present
        if any(k in data for k in ['weight_kg', 'body_fat_pct', 'bmi']):
            body = BodyMetric(user_id=user.id, source='apple_health',
                              date=entry.date)
            for field in ['weight_kg', 'body_fat_pct', 'bmi']:
                if field in data:
                    setattr(body, field, data[field])
            db.session.add(body)

        db.session.commit()
        return jsonify(data)

    @app.route('/api/sync/renpho', methods=['POST'])
    def sync_renpho():
        """Trigger Renpho data sync."""
        user = User.query.first()
        if not user or not user.renpho_email:
            return jsonify({"error": "Renpho not connected"}), 400

        from api.renpho_client import RenphoClient
        client = RenphoClient(email=user.renpho_email)
        try:
            data = client.sync_daily_data()
            body = BodyMetric(user_id=user.id, source='renpho')
            body.date = date.fromisoformat(data.get('date', date.today().isoformat()))
            for field in ['weight_kg', 'bmi', 'body_fat_pct', 'muscle_mass_kg',
                           'bone_mass_kg', 'water_pct', 'visceral_fat',
                           'basal_metabolism', 'metabolic_age', 'protein_pct']:
                if field in data and data[field] is not None:
                    setattr(body, field, data[field])
            db.session.add(body)
            db.session.commit()
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── Connection Setup ─────────────────────────────────────────────

    @app.route('/api/connect/whoop', methods=['POST'])
    def connect_whoop():
        """Store Whoop OAuth credentials."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400
        data = request.json
        user.whoop_access_token = data.get('access_token')
        user.whoop_refresh_token = data.get('refresh_token')
        db.session.commit()
        return jsonify({"status": "connected"})

    @app.route('/api/connect/renpho', methods=['POST'])
    def connect_renpho():
        """Store Renpho credentials."""
        user = User.query.first()
        if not user:
            return jsonify({"error": "Setup profile first"}), 400
        data = request.json
        user.renpho_email = data.get('email')
        # In production, hash the password
        user.renpho_password_hash = data.get('password')
        db.session.commit()
        return jsonify({"status": "connected"})

    return app


# Create the app instance
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
