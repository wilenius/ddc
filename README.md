# DDC Tournament Manager

A Django-based tournament management system specifically designed for Double Disc Court (DDC) tournaments. This initial release mostly supports Cade Loving's monarch of the court style tournaments.

## Features

- Tournament Management
  - Create and manage tournaments
  - Support for Cade Loving's 8-player King of the Court format
  - Multiple sets scoring system
  - Point difference tracking
  - Match history and statistics

- User Roles and Permissions
  - Admin: Full access to create tournaments and manage players
  - Player: Can create tournaments and record scores
  - Spectator: View-only access to tournaments and results

- Match Scoring
  - Support for multiple sets (up to 3)
  - Automatic point difference calculation
  - Match result logging
  - Real-time standings updates

## Setup

### Development Setup

1. Clone the repository:
   ```bash
   git clone [repository-url]
   cd ddc
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   # Copy the example environment file
   cp .env.example .env

   # Generate a new SECRET_KEY
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

   # Edit .env and set your SECRET_KEY and other settings
   # For development, the defaults in .env.example are usually fine
   ```

   **Required settings in `.env`:**
   - `SECRET_KEY` - Generate a new one (see command above)
   - `DEBUG` - Set to `True` for development, `False` for production
   - `STATIC_ROOT` - Path where static files will be collected
   - `ALLOWED_HOSTS` - Comma-separated list of allowed hostnames

   See `.env.example` for all available options.

5. Apply database migrations:
   ```bash
   python manage.py migrate
   ```
   *Note: Tournament archetypes are automatically populated after migrations*

6. Populate default archetype notes:
   ```bash
   python manage.py populate_archetype_notes
   ```

7. Collect static files:
   ```bash
   python manage.py collectstatic --noinput
   ```

8. Create a superuser (admin account):
   ```bash
   python manage.py createsuperuser
   ```

9. Run the development server:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

9. Access the application:
   - Main site: http://127.0.0.1:8000/
   - Admin interface: http://127.0.0.1:8000/admin/

### Getting started

After running the setup steps above to create users navigate to the admin panel at `http://localhost:8000/admin/`. Create a user with `administrator` role that can be used in the application for creating tournaments and players.

### Production Deployment

For production deployment, follow the development setup steps with these modifications:

1. **Environment Configuration:**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` with production values:
   ```
   SECRET_KEY=<generate-new-secret-key>
   DEBUG=False
   STATIC_ROOT=/var/www/ddc/staticfiles  # Or your production path
   ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
   ```

2. **Security Checklist:**
   - Never commit your `.env` file to version control
   - Use a strong, randomly generated `SECRET_KEY`
   - Set `DEBUG=False` in production
   - Configure proper `ALLOWED_HOSTS`
   - Use a production-grade database (PostgreSQL recommended)
   - Set up HTTPS/SSL
   - Configure proper file permissions for `.env` (e.g., `chmod 600 .env`)

3. **Static Files:**
   Production deployments typically use a web server (like Nginx) to serve static files:
   ```bash
   python manage.py collectstatic --noinput
   ```

4. **Database:**
   For production, consider using PostgreSQL instead of SQLite:
   ```bash
   # In .env:
   DATABASE_URL=postgresql://user:password@localhost/dbname
   ```
   Then install: `pip install psycopg2-binary`

## Running Tests

To run all tests:
```bash
python manage.py test tournament_creator.tests
```

To run specific test categories:
```bash
python manage.py test tournament_creator.tests.test_models
python manage.py test tournament_creator.tests.test_views
python manage.py test tournament_creator.tests.test_tournament_logic
python manage.py test tournament_creator.tests.test_scoring
```

## Starting Fresh

If you need to reset your database:
```bash
rm db.sqlite3
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## Exporting and Loading Test Cases

You can use Django's dumpdata command to export your database to a JSON fixture:
```bash
python manage.py dumpdata tournament_creator --indent 2 > test_fixture.json
```
This exports all data from the tournament_creator app. To restore it later to an empty database:
```bash
python manage.py loaddata test_fixture.json
```
If you want to be more selective and only export specific models:
```bash
python manage.py dumpdata tournament_creator.Player tournament_creator.TournamentChart tournament_creator.Matchup tournament_creator.MatchScore tournament_creator.PlayerScore --indent 2 > test_fixture.json
```
Before loading the fixture into a clean database, make sure to:
  1. Run migrations: python manage.py migrate
  2. Then load the data: python manage.py loaddata test_fixture.json


## Signal Notification Backend Setup

This application can send match result updates via Signal. This requires an external service, `signal-cli-rest-api`, to be running and accessible.

### 1. Dependency: `signal-cli-rest-api`

You must first set up and run the `signal-cli-rest-api`. This service acts as a bridge between this Django application and the Signal network.
-   **Project and Setup Instructions**: [https://github.com/bbernhard/signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api)

Ensure that the `signal-cli` instance linked to the REST API is registered with a phone number that will act as the sender.

### 2. Configuration in Django Admin

Once the `signal-cli-rest-api` is operational, configure the Signal backend in the Django admin panel:

1.  Navigate to the admin panel (usually `http://127.0.0.1:8000/admin/`).
2.  Under the "TOURNAMENT_CREATOR" section, find and click on "Notification backend settings".
3.  Add a new setting or modify an existing one:
    *   If creating a new one, click "Add notification backend setting +".
    *   Select `signal` from the "Backend name" dropdown.
    *   If modifying an existing 'signal' entry, click on its name.

4.  Fill in the configuration fields:
    *   **Signal CLI Rest API URL**: Enter the base URL where your `signal-cli-rest-api` instance is accessible (e.g., `http://localhost:8080`).
    *   **Signal Sender Phone Number**: Provide the full international phone number registered with the `signal-cli` instance that will send the messages (e.g., `+12345678901`).
    *   **Recipient Usernames**: A comma-separated list of Signal usernames (full international phone numbers) to which direct notifications will be sent (e.g., `+19876543210,+15551234567`). This field is optional if Recipient Group IDs are provided.
    *   **Recipient Group IDs**: A comma-separated list of Signal group IDs to which notifications will be sent. The sender phone number (bot) must be a member of these groups. This field is optional if Recipient Usernames are provided.
        *   *Note*: You can obtain group IDs from admin view, there's a button to query them from the API.

5.  **Activation**:
    *   Ensure the **"Is active"** checkbox is ticked for the 'signal' backend to enable sending notifications.
    *   At least one recipient (either in "Recipient Usernames" or "Recipient Group IDs") must be configured for messages to be sent.

6.  Save the changes.

### 3. Message Content

When a match result is recorded or updated, and the Signal backend is active and correctly configured, a notification message will be sent. This message typically includes:
-   The tournament name.
-   The user who recorded the result.
-   Details of the matchup (teams/players, round, court).
-   The action performed (e.g., result created/updated).
-   The scores reported.

## User Roles

1. Admin
   - Create/edit/delete tournaments
   - Manage players
   - Record and edit match results
   - Access all features

2. Player
   - Create tournaments
   - Record match results
   - View all tournament data

3. Spectator
   - View tournaments
   - View match results and standings
   - No editing capabilities

## Development

- Built with Django 5.1
- Uses SQLite database (can be configured for other databases)
- Includes comprehensive test suite
- Follows Django best practices for security and performance

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the test suite
5. Submit a pull request

## TODO

1. Tournament creator role
2. Group support for individual pods
3. per pod player / creator / admin rights
4. Tournament types: doubles league (Helsinki winter), MoC league (Florida winter), dynamic MoC (German/Finnish style)
5. Tournament sign-up system
6. What else?

## License

GPL
