Step 6 - Update sqlite_1.py to work with PostgreSQL

Find your sqlite_1.py file. Replace the entire content with this:
python
Copy
Download

import pandas as pd
from sqlalchemy import create_engine, inspect
import os

# Get database URL from environment (Render provides this) or fallback to local SQLite
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///my_database.db')

# Fix for Render's PostgreSQL URL format
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Create engine (works with both SQLite locally and PostgreSQL on Render)
engine = create_engine(DATABASE_URL)

folder_path = '.'
os.chdir(folder_path)

csv_files = [
    'goals.csv',
    'match_cum_agg_stats.csv',
    'matches.csv',
    'team_match_stats.csv',
    'referees.csv',
    'teams.csv'
]

print(f"--- Starting Import into {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else 'local SQLite'} ---")

for file in csv_files:
    table_name = file.replace('.csv', '')

    try:
        df = pd.read_csv(file)
        df.to_sql(table_name, con=engine, if_exists='replace', index=False)
        print(f"Successfully imported: {table_name}")
    except Exception as e:
        print(f"Error importing {file}: {e}")

print("\n--- Final Table Stats ---")
inspector = inspect(engine)
tables = inspector.get_table_names()

for table in tables:
    count = pd.read_sql(f"SELECT COUNT(*) FROM {table}", engine).iloc[0, 0]
    print(f"Table: {table.ljust(20)} | Rows: {count}")

print("Database is ready for use.")

What changed:

    Added DATABASE_URL from environment variable (Render provides this)

    Added PostgreSQL URL fix (converts postgres:// to postgresql://)

    The script now works on both your local machine (SQLite) and Render (PostgreSQL)

Note: This script assumes your CSV files are in the root of your repository.

When you've made this change, say "next step".
