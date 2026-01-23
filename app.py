import sqlite3, os, json
import requests
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from flask.helpers import flash
from flask import send_from_directory


app = Flask(__name__)

# Database initialization
DATABASE = 'albums.db'
UPLOAD_FOLDER = 'static/audio/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
import os

DISCOGS_API_TOKEN = os.getenv("DISCOGS_API_TOKEN")
DISCOGS_USER_AGENT = os.getenv("DISCOGS_USER_AGENT", "invy/0.1")
DISCOGS_USERNAME = os.getenv("DISCOGS_USERNAME");
DISCOGS_API_URL = "https://api.discogs.com/database/search"
DISCOGS_API_USER_URL = "https://api.discogs.com/users"

def init_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist TEXT NOT NULL,
            title TEXT NOT NULL,
            release_date TEXT,
            genre TEXT,
            stream_link TEXT,
            notes TEXT,
            mp3_file TEXT,
            copies INTEGER DEFAULT 1,
            formats TEXT,
            cover_image TEXT
        )
    ''')
    conn.commit()
    conn.close()

## Discogs Integrations ##
@app.route('/sync_collection', methods=['POST'])
def sync_collection():
    username = DISCOGS_USERNAME  # Replace with the actual username
    headers = {"User-Agent": DISCOGS_USER_AGENT}
    params = {"token": DISCOGS_API_TOKEN}
    page = 1
    total_pages = 1
    try:
        while page <= total_pages:
            response = requests.get(
                f"{DISCOGS_API_USER_URL}/{username}/collection/folders/0/releases",
                headers=headers,
                params={**params, "page": page, "per_page": 50}
            )
            if response.status_code != 200:
                print(f"Error fetching collection: {response.json()}")
                return jsonify({'success': False, 'message': 'Error fetching collection'})

            data = response.json()
            total_pages = data["pagination"]["pages"]

            with sqlite3.connect("albums.db") as connection:
                cursor = connection.cursor()

                for release in data["releases"]:
                    artist = release["basic_information"]["artists"][0]["name"]
                    title = release["basic_information"]["title"]
                    release_date = release["basic_information"].get("year", None)
                    genre = release["basic_information"].get("genres", [None])[0]
                    cover_url = release["basic_information"]["cover_image"]

                    # Check if the album already exists
                    cursor.execute('''
                    SELECT * FROM albums WHERE artist = ? AND title = ?
                    ''', (artist, title))
                    existing_album = cursor.fetchone()

                    if not existing_album:
                        # Insert the new album
                        cursor.execute('''
                        INSERT INTO albums (artist, title, release_date, genre)
                        VALUES (?, ?, ?, ?)
                        ''', (artist, title, release_date, genre))
                        connection.commit()  # Commit changes after processing all releases on the page
                        download_thumbnail(artist, title, cover_url)
                        print(f"Added album: {title} by {artist}")
                    else:
                        print(f"Album '{title}' by '{artist}' already exists.")

                print(f"Page {page} of {total_pages} processed.")
                page += 1

        return jsonify({'success': True})
    except Exception as e:
        # Handle any error during the process and return a failure message
        return jsonify({'success': False, 'message': str(e)})

@app.route('/fetch_discogs', methods=['GET'])
def fetch_discogs():
    artist = request.args.get('artist')
    title = request.args.get('title')

    if not artist or not title:
        return jsonify({"success": False, "error": "Missing artist or title."})

    # Search Discogs for the release
    params = {
        "artist": artist,
        "release_title": title,
        "type": "master",
        "token": DISCOGS_API_TOKEN
    }

    response = requests.get(DISCOGS_API_URL, params=params)
    if response.status_code == 200:
        results = response.json().get('results')
        if results:
            # Extract the first result
            result = results[0]
            return jsonify({
                "success": True,
                "artist": result.get("artist"),
                "title": result.get("title"),
                "release_date": result.get("year"),
                "genre": result.get("genre", [""])[0],
                "album_cover": result.get("cover_image")
            })

    return jsonify({"success": False, "error": "No results found."}) 

# Modify the function to fetch the album cover and download it locally
def fetch_thumbnail_from_discogs(artist, title):
    # Replace 'YOUR_DISCOGS_TOKEN' with your actual Discogs API token
    discogs_token = DISCOGS_API_TOKEN
    discogs_api_url = DISCOGS_API_URL

    params = {
        'artist': artist,
        'title': title,
        'format': 'album',
        'type': 'release',
        'token': discogs_token  # Include the token for authentication
    }

    try:
        response = requests.get(discogs_api_url, params=params)
        response.raise_for_status()  # Raise an HTTPError if the response was unsuccessful
        data = response.json()
        print(data)

        # Step 2: Check if results exist
        if data.get('results'):
            results = data['results']

            # Attempt to find a valid master_id
            for result in results:
                master_id = result.get('master_id')
                if master_id and master_id != 0:  # Check if master_id is valid
                    # Step 3: Fetch data from the Master Release endpoint
                    master_api_url = f"https://api.discogs.com/masters/{master_id}"
                    master_response = requests.get(master_api_url, headers={"Authorization": f"Discogs token={discogs_token}"})
                    master_response.raise_for_status()
                    master_data = master_response.json()

                    # Step 4: Retrieve the primary thumbnail
                    if 'images' in master_data and master_data['images']:
                        for image in master_data['images']:
                            if image.get('type') == 'primary':  # Prioritize primary images
                                print(f"Found master primary image: {image['uri']}")
                                return image['uri']
                    
                    # Fallback to the first image if no primary found
                    if 'images' in master_data and master_data['images']:
                        print(f"Found fallback master image: {master_data['images'][0]['uri']}")
                        return master_data['images'][0]['uri']
            
            # If no valid master_id is found, fallback to release thumbnails
            for result in results:
                if 'thumb' in result and result['thumb']:
                    print(f"Found release thumbnail: {result['thumb']}")
                    return result['thumb']
        
        else:
            print("No results found on Discogs for this album.")
            return None

    except requests.RequestException as e:
        print(f"Error fetching data from Discogs: {e}")
        return None


@app.route('/fetch_thumbnail', methods=['POST'])
def fetch_thumbnail():
    """Fetch a thumbnail from Discogs for a given artist and title."""
    try:
        # Parse JSON payload
        data = request.get_json()
        artist = data.get('artist')
        title = data.get('title')
        album_id = data.get('album_id')  # Pass the album ID from the form

        if not artist or not title:
            return jsonify({'success': False, 'error': 'Artist and title are required.'}), 400

        print("Fetching thumbnail for:", artist, title)

        # Fetch the thumbnail URL from Discogs
        thumbnail_url = fetch_thumbnail_from_discogs(artist, title)

        if not thumbnail_url:
            return jsonify({'success': False, 'error': 'No thumbnail found on Discogs.'}), 404

        # Call the download_thumbnail function and return its response
        response = download_thumbnail(artist, title, thumbnail_url)
        return response  # Ensure that the response from download_thumbnail is returned

    except Exception as e:
        print(f"An error occurred in fetch_thumbnail: {e}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred.'}), 500

def download_thumbnail(artist, title, thumbnail_url):
    try:
        # Attempt to download and save the image locally with headers
        headers = {
            'User-Agent': DISCOGS_USER_AGENT,  # Replace with your app's name/version
        }
        response = requests.get(thumbnail_url, headers=headers, stream=True)

        if response.status_code == 200:
            # Generate a filename and save locally
            filename = f"{artist}_{title}.jpg".replace(" ", "_")
            local_path = os.path.join('static/thumbnails', filename)

            os.makedirs('static/thumbnails', exist_ok=True)
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)

            print(f"Thumbnail saved locally at: {local_path}")

            # Update the database with the new thumbnail filename
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM albums WHERE artist = ? AND title = ?', (artist, title))
            result = cursor.fetchone()

            if result:  # Ensure the album exists
                album_id = result[0]
                cursor.execute(
                    "UPDATE albums SET cover_image = ? WHERE id = ?",
                    (filename, album_id),
                )
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'thumbnail_path': local_path}), 200
            else:
                conn.close()
                print("Album not found in the database.")
                return jsonify({'success': False, 'error': 'Album not found in database.'}), 404
        else:
            print(f"Error downloading thumbnail. HTTP status: {response.status_code}")
            return jsonify({'success': False, 'error': 'Failed to download thumbnail from Discogs.'}), 500

    except Exception as e:
        # Log the exception and return an error response
        print(f"An error occurred: {e}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred.'}), 500



def get_existing_artists_and_genres():
    """Fetch unique artists and genres for dropdowns."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT artist FROM albums ORDER BY artist')
    artists = [row[0] for row in cursor.fetchall()]
    cursor.execute('SELECT DISTINCT genre FROM albums ORDER BY genre')
    genres = [row[0] for row in cursor.fetchall()]
    conn.close()
    return artists, genres


@app.route("/")
def index():
    # optional: keep / as Albums “home”
    return redirect(url_for("albums_page"))


@app.route("/albums")
def albums_page():
    """Render the Albums page with the list of albums."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM albums ORDER BY artist, title")
    rows = cursor.fetchall()
    conn.close()

    # Group albums by artist
    albums = {}
    genres = set()

    for row in rows:
        artist = row[1]
        genre = row[4] or ""
        if genre.strip():
            genres.add(genre.strip())

        album = {
            "id": row[0],
            "title": row[2],
            "release_date": row[3],
            "genre": row[4],
            "stream_link": row[5],
            "notes": row[6],
            "mp3_file": row[7],
            "formats": json.loads(row[9]) if row[9] and isinstance(row[9], str) else [],
            "cover_image": row[10],
        }
        albums.setdefault(artist, []).append(album)

    unique_genres = sorted(genres, key=lambda s: s.lower())

    return render_template("albums.html", albums=albums, unique_genres=unique_genres)


@app.route("/gear")
def gear_page():
    return render_template("gear.html")


@app.route("/household")
def household_page():
    return render_template("household.html")


@app.route("/local")
def local_page():
    return render_template("local.html")


@app.route('/add', methods=['GET', 'POST'])
def add_album():
    """Add a new album to the database."""
    if request.method == 'POST':
        artist = request.form['artist']
        title = request.form['title']
        release_date = request.form['release_date']
        genre = request.form['genre']
        stream_link = request.form['stream_link']
        notes = request.form['notes']
        cover_url = request.form['cover_url']

        # Handle file upload
        mp3_file = request.files['mp3_file']
        mp3_filename = None
        if mp3_file and mp3_file.filename.endswith('.mp3'):
            mp3_filename = f"{artist}-{title}.mp3".replace(" ", "_")
            mp3_path = os.path.join(app.config['UPLOAD_FOLDER'], mp3_filename)
            mp3_file.save(mp3_path)

        # Handle formats (make sure it's a list)
        selected_formats = request.form.getlist('formats')  # This will be a list of formats from the form
        if selected_formats:  # If new formats were submitted
            formats_json = json.dumps(selected_formats)  # Convert the list to JSON
        else:
            formats_json ="{}"


        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO albums (artist, title, release_date, genre, formats, stream_link, mp3_file, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (artist, title, release_date, genre, formats_json, stream_link, mp3_filename, notes))
        conn.commit()
        conn.close()

        if cover_url:
            download_thumbnail(artist, title, cover_url)

        return redirect(url_for('index'))

    # Get existing artists and genres for dropdowns
    artists, genres = get_existing_artists_and_genres()
    return render_template("add.html", artists=artists, genres=genres)


@app.route('/edit/<int:album_id>', methods=['GET', 'POST'])
def edit_album(album_id):
    """Edit an existing album."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    if request.method == 'POST':
        artist = request.form['artist']
        title = request.form['title']
        release_date = request.form['release_date']
        genre = request.form['genre']
        stream_link = request.form['stream_link']
        notes = request.form['notes']

        # Cover image handling (keep current unless fetch_cover is on)
        cover_image_path = None
        if request.form.get('fetch_cover') == 'on':
            cover_image_path = fetch_thumbnail_from_discogs(artist, title)
        else:
            cursor.execute('SELECT cover_image FROM albums WHERE id = ?', (album_id,))
            result = cursor.fetchone()
            cover_image_path = result[0] if result else None

        # Handle file upload
        mp3_file = request.files.get('mp3_file')
        mp3_filename = None

        if mp3_file and mp3_file.filename and mp3_file.filename.lower().endswith('.mp3'):
            mp3_filename = f"{artist}-{title}.mp3".replace(" ", "_")
            mp3_path = os.path.join(app.config['UPLOAD_FOLDER'], mp3_filename)
            mp3_file.save(mp3_path)
        else:
            cursor.execute('SELECT mp3_file FROM albums WHERE id = ?', (album_id,))
            current_mp3 = cursor.fetchone()
            mp3_filename = current_mp3[0] if current_mp3 else None

        # Handle formats
        selected_formats = request.form.getlist('formats')
        if selected_formats:
            formats_json = json.dumps(selected_formats)
        else:
            cursor.execute('SELECT formats FROM albums WHERE id = ?', (album_id,))
            current_formats = cursor.fetchone()
            formats_json = current_formats[0] if current_formats else json.dumps([])

        cursor.execute('''
            UPDATE albums
            SET artist = ?, title = ?, release_date = ?, genre = ?, stream_link = ?, notes = ?, mp3_file = ?, formats = ?, cover_image = ?
            WHERE id = ?
        ''', (artist, title, release_date, genre, stream_link, notes, mp3_filename, formats_json, cover_image_path, album_id))

        conn.commit()
        conn.close()
        return redirect(url_for('albums_page'))

    # GET: Fetch album details for pre-filling the form
    cursor.execute('SELECT * FROM albums WHERE id = ?', (album_id,))
    album = cursor.fetchone()
    conn.close()

    if not album:
        return "Album not found", 404

    # IMPORTANT: formats is column 9 in your schema usage elsewhere
    formats = json.loads(album[9]) if album[9] and isinstance(album[9], str) else []

    artists, genres = get_existing_artists_and_genres()

    album_data = {
        'id': album[0],
        'artist': album[1],
        'title': album[2],
        'release_date': album[3],
        'genre': album[4],
        'stream_link': album[5],
        'notes': album[6],
        'mp3_file': album[7],
        'formats': formats,
        'cover_image': album[10],  # matches your index/albums template
    }

    return render_template("edit.html", album=album_data, artists=artists, genres=genres)


@app.route('/delete/<int:album_id>', methods=['POST'])
def delete_album(album_id):
    # Find and delete the album from the database
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Retrieve the album to delete its MP3 file if it exists
    cursor.execute("SELECT mp3_file FROM albums WHERE id = ?", (album_id,))
    mp3_file = f"cursor.fetchone()"
    mp3_path = os.path.join(app.config['UPLOAD_FOLDER'],mp3_file)

    # Delete the album record from the database
    cursor.execute("DELETE FROM albums WHERE id = ?", (album_id,))
    conn.commit()
    conn.close()

    # Delete the MP3 file if it exists
    if mp3_path and mp3_path[0] and os.path.exists(mp3_path[0]):
        os.remove(mp3_path[0])

    # flash("Album deleted successfully!", "success")
    return redirect('/')

@app.route("/wiki/")
@app.route("/wiki/<path:filename>")
def wiki(filename="index.html"):
    return send_from_directory(QUARTZ_PUBLIC, filename)

@app.route("/savewiki", methods=["POST"])
def save_tiddlywiki():
    """Handle saving edits to TiddlyWiki."""
    try:
        # Get the updated TiddlyWiki content from the request
        updated_content = request.data.decode("utf-8")
        
        # Save the content back to the TiddlyWiki file
        with open('static/tiddlywiki', "w", encoding="utf-8") as f:
            f.write(updated_content)
        
        return jsonify({"status": "success", "message": "TiddlyWiki saved successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    init_db()  # Ensure the database and table are initialized
    app.run(host="0.0.0.0", port="8080")  # Use 0.0.0.0 to make it accessible over the network
