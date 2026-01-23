import sqlite3

# Database file
DATABASE = 'albums.db'

def update_database_schema():
    """Update the database schema to add 'formats' column."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Add the 'formats' column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE albums ADD COLUMN formats TEXT")
        print("Added 'formats' column.")
    except sqlite3.OperationalError:
        print("'formats' column already exists.")

    conn.commit()
    conn.close()
    print("Database schema updated successfully.")

if __name__ == '__main__':
    update_database_schema()

