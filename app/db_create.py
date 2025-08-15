from config import SQLALCHEMY_DATABASE_URI  # ensures config is loaded
from app import db
import os

# Create all tables if they don't exist (for local/dev use).
# For production/deploy use Alembic/Flask-Migrate: `flask db upgrade`
if __name__ == "__main__":
    if not os.path.exists("app.db"):
        db.create_all()
        print("Database created.")
    else:
        print("Database already exists.")
