import sqlite3

# Database file
DATABASE = 'albums.db'

def update_database_schema():
    """Update the database schema to add 'copies' column."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Add the 'copies' column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE albums ADD COLUMN copies INTEGER DEFAULT 1")
        print("Added 'copies' column.")
    except sqlite3.OperationalError:
        print("'copies' column already exists.")

    # Update existing rows with a default value for 'copies' if it's NULL
    cursor.execute("UPDATE albums SET copies = 1 WHERE copies IS NULL")

    conn.commit()
    conn.close()
    print("Database schema updated successfully.")

if __name__ == '__main__':
    update_database_schema()

