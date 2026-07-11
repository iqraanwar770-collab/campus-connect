# EduVerse — Campus Connect (Flask)

Modern student community platform: **Notes portal, Blood donors, Lost & Found**.

## Run on Windows / Mac / Linux

```bash
pip install -r requirements.txt
python app.py
```

The server starts at **http://127.0.0.1:5000** and opens your default browser automatically.

## Structure

```
campus_connect/
├── app.py                 # Flask backend + SQLite CRUD
├── requirements.txt
├── database.db            # auto-created on first run
├── static/
│   ├── css/style.css      # Royal blue / purple theme
│   └── uploads/           # user-uploaded notes
└── templates/
    ├── base.html   home.html   login.html   register.html
    ├── dashboard.html   notes.html   donors.html
    ├── lostfound.html   info.html
```

## Features

- Login / Register / Logout (hashed passwords, sessions)
- Dashboard with stat cards + quick actions
- **Notes**: upload PDF / DOC / DOCX / PPT / PPTX / images, search, download, delete
- **Blood Donors**: register, search by name/city, filter by blood group, delete with confirmation
- **Lost & Found**: add / view / search / delete posts
- Professional footer (About / Contact / Privacy / Terms)
- Fully responsive Bootstrap 5 UI
