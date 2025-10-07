# AGENTS.md

This file provides guidance to AI coding assistants (Claude Code, etc.) when working with code in this repository.

## Project Overview

DDC Tournament Manager is a Django-based application for managing Double Disc Court tournaments. The system supports various tournament formats, with a focus on "Monarch of the Court" (MoC) and Swedish-style doubles (pairs) tournaments.

## Core Commands

### Setup and Installation

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Apply database migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Run the test server
source venv/bin/activate && python manage.py runserver 0.0.0.0:8000
```

### Development

When adding features, don't start the development server – let the user test features by themselves. Just prompt the user to test when ready.

### Testing

```bash
# Run all tests
python manage.py test tournament_creator.tests

# Run specific test categories
python manage.py test tournament_creator.tests.test_models
python manage.py test tournament_creator.tests.test_views
python manage.py test tournament_creator.tests.test_tournament_logic
python manage.py test tournament_creator.tests.test_scoring
python manage.py test tournament_creator.tests.test_rankings
python manage.py test tournament_creator.tests.test_tournament_formats
python manage.py test tournament_creator.tests.test_notifications
python manage.py test tournament_creator.tests.test_tiebreaks
```

## Architecture

The application is built on Django 5.1. Check exact requirements from requirements.txt, and use the context7 MCP server to check syntax and documentation if necessary.

The application follows a modular design:

### Core Data Model

1. **Players and Pairs**
   - `Player` model tracks individual players with rankings
   - `Pair` model groups two players together with combined ranking and seed
   - Pairs are created in selection order (not ranking order)

2. **Tournaments**
   - `TournamentChart` is the main container for a tournament
   - Supports both single-stage and multi-stage tournaments
   - Linked to players (MoC) or pairs (doubles) based on tournament type
   - Fields: `name`, `date`, `end_date`, `number_of_stages`, `number_of_rounds`, `number_of_courts`
   - Tournament categories: `MOC` (Monarch of the Court) or `PAIRS` (doubles)

3. **Multi-Stage Tournaments**
   - `Stage` model represents individual stages within a tournament
   - Each stage has: `stage_number`, `stage_type`, `name`, `scoring_mode`
   - Stage types: `POOL` (pool play), `PLAYOFF` (playoffs/finals), `ROUND_ROBIN`
   - Scoring modes: `CUMULATIVE` (scores carry over) or `RESET` (fresh start)
   - Matchups are linked to specific stages

4. **Matchups and Scoring**
   - `Matchup` represents a single match (between pairs or individuals)
   - Linked to a specific `Stage` (can be null for single-stage tournaments)
   - `MatchScore` tracks scores for each set within a matchup
   - `PlayerScore` aggregates individual player performance (MoC tournaments)
   - `PairScore` aggregates pair performance (doubles tournaments)

5. **Notifications**
   - Support for email, Signal, and Matrix notifications
   - Per-tournament notification settings
   - `NotificationBackendSetting` for global configuration
   - `NotificationLog` tracks notification history

### Tournament Structure

The application uses an archetypal inheritance pattern for tournament formats:

1. **Base Classes**
   - `TournamentArchetype` (database model) - stores tournament metadata
   - `PairsTournamentArchetype` (abstract) - base for doubles tournaments
   - `MoCTournamentArchetype` (abstract) - base for individual tournaments

2. **Concrete Implementations**
   - **Pairs tournaments**: `TwoPairsFormat` through `TenPairsFormat`
   - **MoC tournaments**: `MonarchOfTheCourt5` through `MonarchOfTheCourt16`
   - Each format defines its own `schedule` (matchup patterns)
   - Use `get_implementation()` to get code implementation from database archetype

3. **Key Methods**
   - `calculate_rounds(num_players)` - determines number of rounds
   - `calculate_courts(num_players)` - determines number of courts
   - `generate_matchups(tournament_chart, players, stage=None)` - creates matchups
   - `get_automatic_wins(num_players)` - returns dict of automatic wins (for balancing)

### User Authentication

The system has three primary user roles:
- **Admin**: Full access to create tournaments and manage players
- **Player**: Can create tournaments and record scores
- **Spectator**: Can view tournaments and record scores (same as Player for scoring)

### Name Display

- Tournaments support two name display formats: `FIRST` (first names) or `LAST` (last names)
- Names are disambiguated automatically (adds last name initial if needed)
- Display names are set before grouping/filtering to maintain object references

## Key Workflows

1. **Tournament Creation**
   - Select tournament category (MOC or PAIRS)
   - Select number of stages (1 for single-stage, 2+ for multi-stage)
   - Select players (for MoC) in desired order
   - For pairs: players are grouped consecutively (1&2, 3&4, etc.) based on selection order
   - Tournament structure (rounds, courts) calculated automatically based on player/pair count
   - Stages are created with matchups generated for each stage

2. **Match Scoring**
   - Scores recorded per matchup with multiple sets
   - Point differences calculated automatically
   - Player/pair scores updated in real-time
   - Score changes logged in `MatchResultLog`
   - Notifications sent based on tournament settings

3. **Multi-Stage Tournament Navigation**
   - Stages displayed as tabs in the UI
   - Active stage tab persists across page reloads using sessionStorage
   - Each stage shows its own set of matchups
   - Scores can be cumulative or reset per stage

4. **Tournament Management**
   - View matchups by stage, round, and court
   - Track player/pair performance and rankings
   - Download tournament results as text
   - Log history of match result changes
   - Optional tournament structure display

5. **Tiebreaking**
   - MoC tournaments: head-to-head record, then point differential
   - Automatic wins added to total wins (for formats like 11-player MoC)
   - Tiebreak resolution display in standings

## Important Implementation Notes

### Archetype Pattern
When working with tournament creation:
```python
# Get database archetype
archetype = TournamentArchetype.objects.get(name="...")

# Get code implementation for matchup generation
from tournament_creator.models.tournament_types import get_implementation
archetype_impl = get_implementation(archetype)

# Generate matchups with stage support
archetype_impl.generate_matchups(tournament, players, stage=stage)
```

### Display Names
Always set display names BEFORE grouping or filtering:
```python
# CORRECT: Set display names on all objects first
for matchup in all_matchups:
    matchup.pair1.player1.display_name = get_display_name(...)
    # ... set all display names

# THEN group/filter
matchups_by_stage = {stage.id: [m for m in all_matchups if m.stage_id == stage.id]}

# INCORRECT: Don't use QuerySet filter after setting display names
# The filtered QuerySet creates new object instances without the display names
```

### Testing
- Test suite has 65 tests, 62 currently passing
- 3 pre-existing notification test failures (unrelated to multi-stage feature)
- Tests updated to include required fields: `tournament_category`, `number_of_stages`, `name_display_format`
- Form fields use `FIRST` or `LAST` for name_display_format (not `FULL`)

## File Organization

- `tournament_creator/models/base_models.py` - Core models (TournamentChart, Stage, Matchup, Player, Pair)
- `tournament_creator/models/tournament_types.py` - Tournament format implementations
- `tournament_creator/models/scoring.py` - PlayerScore, PairScore, MatchScore
- `tournament_creator/models/notifications.py` - Notification system
- `tournament_creator/views/tournament_views.py` - Tournament CRUD and scoring views
- `tournament_creator/templates/tournament_creator/` - Django templates
- `tournament_creator/tests/` - Test suite

## Recent Major Features

- **Multi-stage tournaments** (feat/multi-stage-tournaments branch)
  - Support for 1+ stages per tournament
  - Stage-based matchup organization
  - Tab navigation with persistence
  - Extensible for future pool play with finals

- **Tournament date ranges**
  - Support for `end_date` field
  - Start date synchronization in UI

- **Expanded tournament formats**
  - Pairs: 2-10 pairs (all round-robin)
  - MoC: 5-16 players (various schedules)
  - Automatic wins for balanced formats (e.g., 11-player MoC)

- **Tiebreak system**
  - Head-to-head records
  - Point differential
  - Automatic win integration

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
