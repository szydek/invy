# Invy (Working Title)

A lightweight Flask-based app for managing personal inventories, notes, and related data.

This repo is set up to run locally using a Python virtual environment and environment variables loaded from a `.env` file.

---

## Requirements

- macOS or Linux  
- Python 3.9+ (3.10 or 3.11 recommended)
- `venv` (comes with Python)

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/invy.git
cd invy
```

---

### 2. Create and activate a virtual environment

If you don’t already have one:

```bash
python3 -m venv ~/venv
```

Activate it:

```bash
source ~/venv/bin/activate
```

---

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

(If `requirements.txt` doesn’t exist yet, install Flask manually:)

```bash
pip install flask python-dotenv
```

---

### 4. Create a `.env` file

In the project root, create a `.env` file for environment variables:

```bash
touch .env
```

Example contents:

```env
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=change-me
```

Adjust as needed for your setup.

---

### 5. Run the app

You can start the app using the provided script:

```bash
./startapp.sh
```

Or manually:

```bash
source ~/venv/bin/activate
source .env
python3 app.py
```

---

### 6. Open in your browser

By default, Flask runs at:

```
http://127.0.0.1:5000
```

---

## `startapp.sh`

For reference, this script does the following:

```sh
. ~/venv/bin/activate
. ./.env
python3 ./app.py
```

- Activates the virtual environment
- Loads environment variables
- Starts the Flask app

---

## Notes

- This app is intended for **local use**
- Databases and uploaded files may be excluded from version control
- If something breaks, try restarting the app after activating the venv again

---

## License

MIT (or TBD)
