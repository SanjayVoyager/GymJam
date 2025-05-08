import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)
from datetime import datetime, timedelta
import random
import json
import os

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database setup (using JSON file)
DB_FILE = 'fitness_data.json'
if not os.path.exists(DB_FILE):
    with open(DB_FILE, 'w') as f:
        json.dump({}, f)

def load_db():
    with open(DB_FILE) as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Conversation states
WEIGHT, WORKOUT, EXERCISE, SETS, REPS, WATER_GOAL, MEAL, CALORIES = range(8)

# Exercise database
EXERCISES = {
    "cardio": ["Running", "Cycling", "Swimming", "Jump Rope"],
    "strength": ["Push-ups", "Pull-ups", "Squats", "Lunges"],
    "flexibility": ["Yoga", "Stretching", "Pilates"]
}

# Main menu keyboard
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Log Weight", callback_data='log_weight'),
         InlineKeyboardButton("🏋️ Log Workout", callback_data='log_workout')],
        [InlineKeyboardButton("💧 Water Tracker", callback_data='water_tracker'),
         InlineKeyboardButton("🍎 Nutrition", callback_data='nutrition')],
        [InlineKeyboardButton("📈 View Progress", callback_data='view_progress'),
         InlineKeyboardButton("🔥 Daily Challenge", callback_data='daily_challenge')],
        [InlineKeyboardButton("⚙️ Settings", callback_data='settings')]
    ])

def update_streak(db, user):
    """Update user's activity streak"""
    today = datetime.now().date()
    last_active_str = db[str(user.id)].get('last_active')
    
    if last_active_str:
        last_active = datetime.strptime(last_active_str, "%Y-%m-%d").date()
        if (today - last_active) == timedelta(days=1):
            db[str(user.id)]['streak'] += 1
        elif (today - last_active) > timedelta(days=1):
            db[str(user.id)]['streak'] = 1  # Reset streak
    else:
        db[str(user.id)]['streak'] = 1
    
    db[str(user.id)]['last_active'] = today.strftime("%Y-%m-%d")
    
    # Check for streak achievements
    streak = db[str(user.id)]['streak']
    achievements = db[str(user.id)]['achievements']
    
    if streak >= 7 and "7-day streak" not in achievements:
        achievements.append("7-day streak")
    if streak >= 30 and "30-day streak" not in achievements:
        achievements.append("30-day streak")

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = load_db()
    
    if str(user.id) not in db:
        db[str(user.id)] = {
            'weight': [],
            'workouts': {},
            'water': {'count': 0, 'goal': 8, 'history': {}},
            'meals': [],
            'calories': {'goal': 2000, 'consumed': 0},
            'last_active': None,
            'streak': 0,
            'achievements': []
        }
        save_db(db)
    
    await update.message.reply_text(
        f"👋 Welcome {user.first_name} to Fitness Tracker Pro!\n"
        "Your complete fitness companion:",
        reply_markup=main_menu_keyboard()
    )

async def show_workout_categories(query):
    buttons = []
    for category in EXERCISES.keys():
        buttons.append([InlineKeyboardButton(
            f"{category.title()} Exercises", 
            callback_data=f'category_{category}'
        )])
    buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')])
    
    await query.edit_message_text(
        "🏋️ Select Workout Category:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def show_exercises(query, category):
    buttons = []
    for exercise in EXERCISES[category]:
        buttons.append([InlineKeyboardButton(
            exercise, 
            callback_data=f'exercise_{exercise.lower().replace(" ", "_")}'
        )])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data='log_workout')])
    
    await query.edit_message_text(
        f"{category.title()} Exercises:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def save_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('exercise_'):
        exercise = query.data.split('_', 1)[1].replace("_", " ").title()
        context.user_data['current_exercise'] = exercise
        
        await query.edit_message_text(
            f"Selected: {exercise}\n"
            "Enter number of sets:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Cancel", callback_data='cancel')]
            ])
        )
        return SETS

async def save_sets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sets = int(update.message.text)
        context.user_data['sets'] = sets
        
        await update.message.reply_text(
            f"Enter number of reps for {sets} sets:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Cancel", callback_data='cancel')]
            ])
        )
        return REPS
    except ValueError:
        await update.message.reply_text(
            "Please enter a valid number (e.g. 3)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Cancel", callback_data='cancel')]
            ])
        )
        return SETS

async def save_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        reps = int(update.message.text)
        user = update.message.from_user
        db = load_db()
        
        exercise = context.user_data['current_exercise']
        sets = context.user_data['sets']
        today = datetime.now().strftime("%Y-%m-%d")
        
        if today not in db[str(user.id)]['workouts']:
            db[str(user.id)]['workouts'][today] = {}
            
        db[str(user.id)]['workouts'][today][exercise] = {
            'sets': sets,
            'reps': reps,
            'time': datetime.now().strftime("%H:%M")
        }
        
        # Update streak
        update_streak(db, user)
        
        save_db(db)
        
        await update.message.reply_text(
            f"✅ Workout logged!\n"
            f"{exercise}: {sets} sets of {reps} reps",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "Please enter a valid number (e.g. 12)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Cancel", callback_data='cancel')]
            ])
        )
        return REPS

async def save_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text)
        user = update.message.from_user
        db = load_db()
        
        db[str(user.id)]['weight'].append({
            'value': weight,
            'date': datetime.now().strftime("%Y-%m-%d")
        })
        save_db(db)
        
        await update.message.reply_text(
            f"✅ Weight {weight}kg saved!",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "Please enter a valid number (e.g. 75.5)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Cancel", callback_data='cancel')]
            ])
        )
        return WEIGHT

async def show_water_tracker(query):
    user = query.from_user
    db = load_db()
    water_data = db[str(user.id)]['water']
    progress = min(int((water_data['count'] / water_data['goal']) * 100), 100)
    progress_bar = "🟩" * int(progress / 10) + "⬜" * (10 - int(progress / 10))
    
    await query.edit_message_text(
        f"💧 Water Tracker\n\n"
        f"Today's intake: {water_data['count']}/{water_data['goal']} glasses\n"
        f"{progress_bar} {progress}%\n\n"
        "Keep hydrating for better performance!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Glass", callback_data='add_water'),
             InlineKeyboardButton("⚙️ Set Goal", callback_data='set_water_goal')],
            [InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]
        ])
    )

async def add_water(query):
    user = query.from_user
    db = load_db()
    db[str(user.id)]['water']['count'] += 1
    save_db(db)
    await show_water_tracker(query)

async def save_water_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        goal = int(update.message.text)
        user = update.message.from_user
        db = load_db()
        db[str(user.id)]['water']['goal'] = goal
        save_db(db)
        
        await update.message.reply_text(
            f"✅ Water goal set to {goal} glasses per day!",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "Please enter a valid number (e.g. 8)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Cancel", callback_data='cancel')]
            ])
        )
        return WATER_GOAL

async def nutrition_menu(query):
    user = query.from_user
    db = load_db()
    calories = db[str(user.id)]['calories']
    
    await query.edit_message_text(
        f"🍎 Nutrition Tracker\n\n"
        f"Calories today: {calories['consumed']}/{calories['goal']} kcal\n\n"
        "Track your meals and calories:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Log Meal", callback_data='log_meal'),
             InlineKeyboardButton("🔥 Log Calories", callback_data='log_calories')],
            [InlineKeyboardButton("⚙️ Set Calorie Goal", callback_data='set_calorie_goal')],
            [InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]
        ])
    )

async def save_meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    meal = update.message.text
    user = update.message.from_user
    db = load_db()
    
    db[str(user.id)]['meals'].append({
        'name': meal,
        'time': datetime.now().strftime("%H:%M"),
        'date': datetime.now().strftime("%Y-%m-%d")
    })
    save_db(db)
    
    await update.message.reply_text(
        f"✅ Meal logged: {meal}",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

async def save_calories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        calories = int(update.message.text)
        user = update.message.from_user
        db = load_db()
        
        db[str(user.id)]['calories']['consumed'] += calories
        save_db(db)
        
        await update.message.reply_text(
            f"✅ {calories} calories logged!",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "Please enter a valid number (e.g. 500)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Cancel", callback_data='cancel')]
            ])
        )
        return CALORIES

async def show_progress(query):
    user = query.from_user
    db = load_db()
    data = db[str(user.id)]
    
    text = "📊 Your Progress\n\n"
    
    # Weight progress
    if data['weight']:
        text += "⚖️ Weight History:\n"
        for entry in data['weight'][-5:]:  # Show last 5 entries
            text += f"{entry['date']}: {entry['value']}kg\n"
        text += "\n"
    
    # Workout progress
    if data['workouts']:
        text += "🏋️ Recent Workouts:\n"
        workouts = list(data['workouts'].items())[-3:]  # Show last 3 workouts
        for workout, exercises in workouts:
            text += f"\n{workout}:\n"
            for exercise, details in exercises.items():
                text += f"  {exercise}: {details['sets']}x{details['reps']}\n"
    
    # Nutrition summary
    text += f"\n🍎 Nutrition Today: {data['calories']['consumed']}/{data['calories']['goal']} kcal"
    
    # Streak
    text += f"\n\n🔥 Current streak: {data['streak']} days"
    
    # Achievements
    if data['achievements']:
        text += "\n\n🏆 Achievements:\n" + "\n".join(data['achievements'])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]
        ])
    )

async def daily_challenge(query):
    challenges = [
        {"name": "Plank Challenge", "desc": "Hold a plank for 2 minutes", "reward": "Core strength boost!"},
        {"name": "Squat Challenge", "desc": "Do 50 bodyweight squats", "reward": "Leg day complete!"},
        {"name": "Hydration Challenge", "desc": "Drink 10 glasses of water", "reward": "Better hydration!"}
    ]
    
    challenge = random.choice(challenges)
    
    await query.edit_message_text(
        f"🔥 Today's Challenge\n\n"
        f"🏆 {challenge['name']}\n"
        f"{challenge['desc']}\n\n"
        f"🎁 Reward: {challenge['reward']}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ I Did It!", callback_data='complete_challenge')],
            [InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]
        ])
    )

async def settings_menu(query):
    user = query.from_user
    db = load_db()
    
    await query.edit_message_text(
        "⚙️ Settings\n\n"
        "Configure your fitness tracker:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💧 Water Goal", callback_data='set_water_goal'),
             InlineKeyboardButton("🔥 Calorie Goal", callback_data='set_calorie_goal')],
            [InlineKeyboardButton("🔔 Notifications", callback_data='notifications')],
            [InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]
        ])
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'log_weight':
        await query.edit_message_text(
            "Enter your current weight (kg):",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Cancel", callback_data='cancel')]
            ])
        )
        return WEIGHT
        
    elif query.data == 'log_workout':
        await show_workout_categories(query)
        return EXERCISE
        
    elif query.data == 'water_tracker':
        await show_water_tracker(query)
        
    elif query.data == 'view_progress':
        await show_progress(query)
        
    elif query.data == 'daily_challenge':
        await daily_challenge(query)
        
    elif query.data == 'nutrition':
        await nutrition_menu(query)
        
    elif query.data == 'settings':
        await settings_menu(query)
        
    elif query.data.startswith('category_'):
        category = query.data.split('_')[1]
        await show_exercises(query, category)
        
    elif query.data == 'add_water':
        await add_water(query)
        
    elif query.data == 'set_water_goal':
        await query.edit_message_text(
            "Enter your daily water goal (glasses):",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Cancel", callback_data='cancel')]
            ])
        )
        return WATER_GOAL
        
    elif query.data == 'log_meal':
        await query.edit_message_text(
            "What did you eat? (e.g. 'Chicken salad')",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Cancel", callback_data='cancel')]
            ])
        )
        return MEAL
        
    elif query.data == 'log_calories':
        await query.edit_message_text(
            "Enter calories consumed:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Cancel", callback_data='cancel')]
            ])
        )
        return CALORIES
        
    elif query.data == 'main_menu':
        await query.edit_message_text(
            "🏠 Main Menu",
            reply_markup=main_menu_keyboard()
        )
        
    elif query.data == 'cancel':
        await cancel(query)

async def cancel(query):
    await query.edit_message_text(
        "Operation cancelled",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

def main():
    application = Application.builder().token("7938237852:AAF_bJ7t_RfvZFNPVYBoFzKtqzgmYKVVIyo").build()
    
    # Conversation handlers
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern='^log_weight$'),
            CallbackQueryHandler(button_handler, pattern='^log_workout$'),
            CallbackQueryHandler(button_handler, pattern='^set_water_goal$'),
            CallbackQueryHandler(button_handler, pattern='^log_meal$'),
            CallbackQueryHandler(button_handler, pattern='^log_calories$')
        ],
        states={
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_weight)],
            EXERCISE: [CallbackQueryHandler(save_exercise, pattern='^exercise_')],
            SETS: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_sets)],
            REPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_workout)],
            WATER_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_water_goal)],
            MEAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_meal)],
            CALORIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_calories)]
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern='^cancel$'),
            CallbackQueryHandler(cancel, pattern='^main_menu$')
        ]
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()