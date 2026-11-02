# Smart Civic Reporter
AI-assisted civic issue reporting web app + an AI-based automated testing framework
(final year project, Software Testing & Automation).

## Setup
```bash
pip install -r requirements.txt
```

## Run
```bash
python app.py
```
Open http://127.0.0.1:5000 (use `localhost`/`127.0.0.1`, not a LAN IP, so camera/mic access works).

Seeded accounts on first run:
- **Admin:** admin@civic.gov / Admin@123
- **Worker (Electricity Board):** worker@civic.gov / Worker@123

## Where your data is stored (permanent)
All records live in ONE fixed folder, no matter where you extract/run the project:

    C:\Users\<you>\AppData\Local\SmartCivicReporter\
        civic.db     users (citizens, workers, admin), complaints, status history,
                     feedback, notifications, green points; analytics are calculated from these
        uploads\     complaint photos and voice notes
        backups\     automatic timestamped copies of civic.db (newest 30 kept)

The app prints these paths every time it starts. Re-extracting a new zip into a new folder
no longer creates a new empty database. NEVER delete civic.db or this folder unless you want a fresh start.

Windows helpers (double-click or run in Command Prompt):
    run_app.bat            install requirements + start the website
    backup_now.bat         make a backup immediately
    open_data_folder.bat   show record counts and open the data folder
    python manage_data.py find      look for old civic.db files from earlier project folders
    python manage_data.py import "C:\path\to\old\civic.db"   bring old data into the permanent folder

## All login credentials

**Admin** (created automatically on first run):
- admin@civic.gov / Admin@123

**Workers** -- one seeded per department automatically on first run, password `Worker@123` for all:
| Email | Department |
|---|---|
| worker.eb@civic.gov | Electricity Board (EB) |
| worker.water@civic.gov | Municipal Water Board |
| worker.pwd@civic.gov | Public Works Department (PWD) |
| worker.sanitation@civic.gov | Municipal Corporation - Sanitation |
| worker.corp@civic.gov | Municipal Corporation - General |
| worker.health@civic.gov | Public Health Department (mosquito control) |
| worker.animal@civic.gov | Animal Control Department (stray animals) |

**Citizens** -- there is no seeded citizen account. Anyone registers their own via `/register`,
then logs in at `/login`. This is intentional: citizens are the public, so they self-serve
signup rather than having a fixed demo account.

## Roles & portals
- **Citizen** -- `/login` -- report issues, track complaints, rate resolved ones, see notifications
- **Worker** -- `/worker/login` -- see and update only your department's complaints
- **Admin** -- `/admin/login` -- see everything, view analytics, create worker accounts

- **🌱 Green Points** -- citizens earn points for civic engagement: +10 for filing a new
  complaint, +3 for confirming/monitoring an issue someone else already reported (duplicate
  merge), +5 for rating a resolved complaint. See total + full history at `/my-points`
  (linked from the nav badge). Admin sees every citizen ranked by points under **Workers**.

## Language toggle
English / Tamil / Hindi switcher in the top nav (`translations.py`). Currently covers the
nav bar, homepage, login, and register pages -- extend by adding more `t('key')` calls in
templates and matching entries in `TRANSLATIONS` for each language.

## Features
- Category dropdown that overrides automatic NLP-based categorization when picked
- Live in-browser camera capture (no gallery upload) with an automatic geotag stamp
- Voice note recording for citizens who find it easier to speak than type
- Draggable-pin map (Leaflet + OpenStreetMap) for precise location confirmation
- Duplicate-report merging with priority escalation
- Full status audit trail with timestamps
- **Admin analytics dashboard** (`/admin/analytics`) -- Chart.js bar/doughnut charts of
  complaints by department, category, status, and priority, plus average citizen rating
- **Citizen feedback/rating** -- once a complaint is marked Completed, the citizen can leave
  a 1-5 star rating and comment
- **Public map** (`/map`, no login needed) -- every complaint plotted as a color-coded pin
  by priority, for transparency
- **Notification log** (`/notifications`) -- in-app stand-in for an email/SMS alert every
  time a citizen's complaint status changes (swap in a real gateway like Twilio/SendGrid by
  calling it wherever a `Notification` row is created in `app.py`)

## Tests
```bash
pytest tests/test_categorizer.py -v
pytest tests/test_api.py -v
python tests/ai_test_prioritizer.py
```
Selenium UI tests need the server running separately:
```bash
python app.py            # terminal 1
pytest tests/test_selenium_ui.py -v   # terminal 2
```

## Note on camera/mic access
Browsers only allow camera/microphone access on `https://` or `http://localhost` /
`http://127.0.0.1`. It will NOT work over a LAN IP like `http://192.168.x.x`.
