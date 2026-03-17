"""Database models for the health tracking application."""

from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """User profile with fitness goals and preferences."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Physical stats
    age = db.Column(db.Integer)
    weight_kg = db.Column(db.Float)
    height_cm = db.Column(db.Float)
    gender = db.Column(db.String(20))
    activity_level = db.Column(db.String(20))  # sedentary, light, moderate, active, very_active

    # Fitness goals
    goal_type = db.Column(db.String(30))  # lose_weight, gain_muscle, maintain, improve_endurance
    target_weight_kg = db.Column(db.Float)
    daily_calorie_target = db.Column(db.Integer)
    daily_protein_g = db.Column(db.Float)
    daily_carbs_g = db.Column(db.Float)
    daily_fat_g = db.Column(db.Float)
    daily_fiber_g = db.Column(db.Float, default=30.0)
    daily_water_ml = db.Column(db.Float, default=2500.0)

    # Weekly allowances
    weekly_alcohol_units = db.Column(db.Float, default=4.0)
    weekly_cheat_meals = db.Column(db.Integer, default=1)
    weekly_rest_days = db.Column(db.Integer, default=2)

    # API connection tokens
    whoop_access_token = db.Column(db.String(500))
    whoop_refresh_token = db.Column(db.String(500))
    apple_health_token = db.Column(db.String(500))
    renpho_email = db.Column(db.String(120))
    renpho_password_hash = db.Column(db.String(256))

    # Relationships
    food_entries = db.relationship('FoodEntry', backref='user', lazy='dynamic')
    fitness_data = db.relationship('FitnessData', backref='user', lazy='dynamic')
    body_metrics = db.relationship('BodyMetric', backref='user', lazy='dynamic')
    symptoms = db.relationship('SymptomEntry', backref='user', lazy='dynamic')
    allowances = db.relationship('WeeklyAllowance', backref='user', lazy='dynamic')

    def get_bmr(self):
        """Calculate Basal Metabolic Rate using Mifflin-St Jeor."""
        if not all([self.weight_kg, self.height_cm, self.age, self.gender]):
            return None
        if self.gender == 'male':
            return 10 * self.weight_kg + 6.25 * self.height_cm - 5 * self.age + 5
        return 10 * self.weight_kg + 6.25 * self.height_cm - 5 * self.age - 161

    def get_tdee(self):
        """Calculate Total Daily Energy Expenditure."""
        bmr = self.get_bmr()
        if bmr is None:
            return None
        multipliers = {
            'sedentary': 1.2, 'light': 1.375, 'moderate': 1.55,
            'active': 1.725, 'very_active': 1.9
        }
        return bmr * multipliers.get(self.activity_level, 1.55)


class FoodEntry(db.Model):
    """Tracks food and drink intake with full nutrient breakdown."""
    __tablename__ = 'food_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    date = db.Column(db.Date, default=date.today)
    meal_type = db.Column(db.String(20))  # breakfast, lunch, dinner, snack, drink

    # Basic info
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image_path = db.Column(db.String(500))
    serving_size = db.Column(db.String(50))
    servings = db.Column(db.Float, default=1.0)

    # Macronutrients (grams)
    calories = db.Column(db.Float, default=0)
    protein_g = db.Column(db.Float, default=0)
    carbs_g = db.Column(db.Float, default=0)
    fat_g = db.Column(db.Float, default=0)
    fiber_g = db.Column(db.Float, default=0)
    sugar_g = db.Column(db.Float, default=0)
    saturated_fat_g = db.Column(db.Float, default=0)
    trans_fat_g = db.Column(db.Float, default=0)

    # Micronutrients
    sodium_mg = db.Column(db.Float, default=0)
    potassium_mg = db.Column(db.Float, default=0)
    calcium_mg = db.Column(db.Float, default=0)
    iron_mg = db.Column(db.Float, default=0)
    magnesium_mg = db.Column(db.Float, default=0)
    zinc_mg = db.Column(db.Float, default=0)
    phosphorus_mg = db.Column(db.Float, default=0)

    # Vitamins
    vitamin_a_mcg = db.Column(db.Float, default=0)
    vitamin_b1_mg = db.Column(db.Float, default=0)
    vitamin_b2_mg = db.Column(db.Float, default=0)
    vitamin_b3_mg = db.Column(db.Float, default=0)
    vitamin_b6_mg = db.Column(db.Float, default=0)
    vitamin_b12_mcg = db.Column(db.Float, default=0)
    vitamin_c_mg = db.Column(db.Float, default=0)
    vitamin_d_mcg = db.Column(db.Float, default=0)
    vitamin_e_mg = db.Column(db.Float, default=0)
    vitamin_k_mcg = db.Column(db.Float, default=0)
    folate_mcg = db.Column(db.Float, default=0)

    # Drink-specific
    is_alcoholic = db.Column(db.Boolean, default=False)
    alcohol_units = db.Column(db.Float, default=0)
    water_ml = db.Column(db.Float, default=0)
    caffeine_mg = db.Column(db.Float, default=0)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'meal_type': self.meal_type,
            'timestamp': self.timestamp.isoformat(), 'calories': self.calories,
            'protein_g': self.protein_g, 'carbs_g': self.carbs_g,
            'fat_g': self.fat_g, 'fiber_g': self.fiber_g,
            'image_path': self.image_path, 'is_alcoholic': self.is_alcoholic,
            'alcohol_units': self.alcohol_units, 'water_ml': self.water_ml,
        }


class FitnessData(db.Model):
    """Fitness data from Whoop, Apple Health, and manual entries."""
    __tablename__ = 'fitness_data'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, default=date.today)
    source = db.Column(db.String(30))  # whoop, apple_health, manual

    # Activity
    steps = db.Column(db.Integer, default=0)
    active_calories = db.Column(db.Float, default=0)
    total_calories_burned = db.Column(db.Float, default=0)
    distance_km = db.Column(db.Float, default=0)
    exercise_minutes = db.Column(db.Integer, default=0)
    exercise_type = db.Column(db.String(50))

    # Heart rate
    resting_heart_rate = db.Column(db.Integer)
    max_heart_rate = db.Column(db.Integer)
    avg_heart_rate = db.Column(db.Integer)
    hrv_ms = db.Column(db.Float)

    # Sleep (from Whoop)
    sleep_hours = db.Column(db.Float)
    sleep_quality_score = db.Column(db.Float)
    rem_sleep_hours = db.Column(db.Float)
    deep_sleep_hours = db.Column(db.Float)
    light_sleep_hours = db.Column(db.Float)
    sleep_latency_min = db.Column(db.Float)
    respiratory_rate = db.Column(db.Float)

    # Whoop-specific
    recovery_score = db.Column(db.Float)
    strain_score = db.Column(db.Float)
    spo2_pct = db.Column(db.Float)
    skin_temp_celsius = db.Column(db.Float)

    def to_dict(self):
        return {
            'id': self.id, 'date': self.date.isoformat(), 'source': self.source,
            'steps': self.steps, 'active_calories': self.active_calories,
            'total_calories_burned': self.total_calories_burned,
            'exercise_minutes': self.exercise_minutes, 'sleep_hours': self.sleep_hours,
            'recovery_score': self.recovery_score, 'strain_score': self.strain_score,
            'hrv_ms': self.hrv_ms, 'resting_heart_rate': self.resting_heart_rate,
        }


class BodyMetric(db.Model):
    """Body composition data from Renpho scale and manual entries."""
    __tablename__ = 'body_metrics'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, default=date.today)
    source = db.Column(db.String(30))  # renpho, manual

    weight_kg = db.Column(db.Float)
    bmi = db.Column(db.Float)
    body_fat_pct = db.Column(db.Float)
    muscle_mass_kg = db.Column(db.Float)
    bone_mass_kg = db.Column(db.Float)
    water_pct = db.Column(db.Float)
    visceral_fat = db.Column(db.Float)
    basal_metabolism = db.Column(db.Float)
    metabolic_age = db.Column(db.Integer)
    protein_pct = db.Column(db.Float)
    subcutaneous_fat_pct = db.Column(db.Float)
    skeletal_muscle_pct = db.Column(db.Float)

    def to_dict(self):
        return {
            'id': self.id, 'date': self.date.isoformat(), 'source': self.source,
            'weight_kg': self.weight_kg, 'bmi': self.bmi,
            'body_fat_pct': self.body_fat_pct, 'muscle_mass_kg': self.muscle_mass_kg,
            'water_pct': self.water_pct, 'visceral_fat': self.visceral_fat,
        }


class SymptomEntry(db.Model):
    """Health symptoms and illness tracking."""
    __tablename__ = 'symptom_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    date = db.Column(db.Date, default=date.today)

    # Symptom details
    symptom_type = db.Column(db.String(100))  # headache, fatigue, nausea, skin_issue, etc.
    description = db.Column(db.Text)
    severity = db.Column(db.Integer)  # 1-10
    image_path = db.Column(db.String(500))
    body_area = db.Column(db.String(50))
    duration_hours = db.Column(db.Float)

    # Analysis results
    ai_analysis = db.Column(db.Text)
    correlations = db.Column(db.Text)  # JSON string of correlated data
    recommendations = db.Column(db.Text)
    resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id, 'date': self.date.isoformat(),
            'symptom_type': self.symptom_type, 'description': self.description,
            'severity': self.severity, 'body_area': self.body_area,
            'image_path': self.image_path, 'ai_analysis': self.ai_analysis,
            'recommendations': self.recommendations, 'resolved': self.resolved,
        }


class WeeklyAllowance(db.Model):
    """Tracks weekly allowances for lifestyle choices."""
    __tablename__ = 'weekly_allowances'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    week_start = db.Column(db.Date, nullable=False)

    # Usage tracking
    alcohol_units_used = db.Column(db.Float, default=0)
    cheat_meals_used = db.Column(db.Integer, default=0)
    rest_days_used = db.Column(db.Integer, default=0)
    dining_out_count = db.Column(db.Integer, default=0)

    # Dynamic adjustments based on performance
    bonus_alcohol_units = db.Column(db.Float, default=0)
    bonus_cheat_meals = db.Column(db.Integer, default=0)
    adjustment_reason = db.Column(db.Text)

    def to_dict(self):
        return {
            'id': self.id, 'week_start': self.week_start.isoformat(),
            'alcohol_units_used': self.alcohol_units_used,
            'alcohol_units_remaining': self.get_remaining_alcohol(),
            'cheat_meals_used': self.cheat_meals_used,
            'cheat_meals_remaining': self.get_remaining_cheat_meals(),
            'rest_days_used': self.rest_days_used,
            'bonus_alcohol_units': self.bonus_alcohol_units,
        }

    def get_remaining_alcohol(self):
        total = self.user.weekly_alcohol_units + self.bonus_alcohol_units
        return max(0, total - self.alcohol_units_used)

    def get_remaining_cheat_meals(self):
        total = self.user.weekly_cheat_meals + self.bonus_cheat_meals
        return max(0, total - self.cheat_meals_used)
