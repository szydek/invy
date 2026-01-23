import sqlite3

# Database file
DATABASE = 'albums.db'

def update_database_schema():
    """Update the database schema to add format and is_favorite columns."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Add new columns if they don't already exist
    try:
        cursor.execute("ALTER TABLE albums ADD COLUMN format TEXT DEFAULT 'Digital'")
        print("Added 'format' column.")
    except sqlite3.OperationalError:
        print("'format' column already exists.")

    try:
        cursor.execute("ALTER TABLE albums ADD COLUMN is_favorite INTEGER DEFAULT 0")
        print("Added 'is_favorite' column.")
    except sqlite3.OperationalError:
        print("'is_favorite' column already exists.")

    conn.commit()
    conn.close()
    print("Database schema updated successfully.")

if __name__ == '__main__':
    update_database_schema()

