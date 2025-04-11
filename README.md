# DDC Tournament Manager

A Django-based tournament management system specifically designed for Double Disc Court (DDC) tournaments. This initial release support only one tournament type: Cade Loving's 8-player King of the Court format. However, it's easy to add tournament types.

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

5. Create a superuser (admin account):
   ```bash
   python manage.py createsuperuser
   ```

6. Run the development server:
   ```bash
   python manage.py runserver
   ```

7. Access the application:
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
