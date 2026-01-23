import sqlite3
import os

# Database file
DATABASE = 'albums.db'

def update_database_schema():
    """Update the database schema to add format and is_favorite columns, and populate existing rows."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Add new columns if they don't already exist
    try:
        cursor.execute("ALTER TABLE albums ADD COLUMN formats TEXT DEFAULT ''")
        print("Added 'formats' column.")
    except sqlite3.OperationalError:
        print("'formats' column already exists.")

    try:
        cursor.execute("ALTER TABLE albums ADD COLUMN is_favorite INTEGER DEFAULT 0")
        print("Added 'is_favorite' column.")
    except sqlite3.OperationalError:
        print("'is_favorite' column already exists.")

    # Update existing rows with default values for 'formats' and 'is_favorite'
    cursor.execute("UPDATE albums SET formats = '' WHERE formats IS NULL")
    cursor.execute("UPDATE albums SET is_favorite = 0 WHERE is_favorite IS NULL")

    # Update 'formats' based on the file extension in 'file_path'
    cursor.execute("SELECT id, file_path FROM albums")
    albums = cursor.fetchall()

    for album in albums:
        album_id, file_path = album
        if file_path:
            # Determine the file format based on file extension
            file_extension = os.path.splitext(file_path)[1].lower()
            if file_extension in ['.mp3', '.wav', '.flac']:
                # Update the 'formats' field with the proper format based on file extension
                cursor.execute("UPDATE albums SET formats = ? WHERE id = ?", (file_extension[1:], album_id))  # Strips the dot
                print(f"Updated formats for album ID {album_id}: {file_extension[1:]}")
            else:
                # If it's not one of the supported formats, just leave the formats empty or assign 'Other'
                cursor.execute("UPDATE albums SET formats = 'Other' WHERE id = ?", (album_id,))
                print(f"Assigned 'Other' format for album ID {album_id} with unsupported file type {file_extension}")
    
    conn.commit()
    conn.close()
    print("Database schema updated and existing data converted successfully.")

if __name__ == '__main__':
    update_database_schema()

