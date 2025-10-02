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

4. Apply database migrations:
   ```bash
   python manage.py migrate
   ```
   *Note: Tournament archetypes are automatically populated after migrations*

5. Collect static files:
   ```bash
   python manage.py collectstatic --noinput
   ```

6. Create a superuser (admin account):
   ```bash
   python manage.py createsuperuser
   ```

7. Run the development server:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

8. Access the application:
   - Main site: http://127.0.0.1:8000/
   - Admin interface: http://127.0.0.1:8000/admin/

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
        *   *Note*: You can usually obtain group IDs using `signal-cli` commands (e.g., `listGroups -g <group_name>`). They are typically base64 encoded strings.

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

## License

GPL
