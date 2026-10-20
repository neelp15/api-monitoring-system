from sqlalchemy import text

from app.db.session import engine


try:
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT current_database(), current_user")
        )
        database, user = result.one()

        print(f"Database: {database}")
        print(f"User: {user}")
        print("Database connection successful!")

finally:
    engine.dispose()