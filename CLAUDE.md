# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DDC Tournament Manager is a Django-based application for managing Double Disc Court tournaments. The system supports various tournament formats, with a focus on the "Monarch of the Court" and Swedish-style pair tournaments.

## Core Commands

### Setup and Installation

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

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

```bash
# Start development server
python manage.py runserver

# Make server accessible on network
python manage.py runserver 0.0.0.0:8000
```

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
```

## Architecture

The application is built on Django 5.1 and follows a modular design:

### Core Data Model

1. **Players and Pairs**
   - `Player` model tracks individual players with rankings
   - `Pair` model groups two players together with combined ranking

2. **Tournaments**
   - `TournamentChart` is the main container for a tournament
   - Linked to players or pairs based on tournament type

3. **Matchups and Scoring**
   - `Matchup` represents a single match (between pairs or individuals)
   - `MatchScore` tracks scores for each set within a matchup
   - `PlayerScore` aggregates player performance across a tournament

### Tournament Structure

The application uses an archetypal inheritance pattern for tournament formats:

1. **Base Classes**
   - `TournamentArchetype` (abstract) defines the interface for all tournament types
   - Derived into `PairsTournamentArchetype` and `MoCTournamentArchetype`

2. **Concrete Implementations**
   - Pair tournaments: `FourPairsSwedishFormat`, `EightPairsSwedishFormat`
   - Individual tournaments: `MonarchOfTheCourt8` (8-player format)

This design makes it easy to add new tournament formats while reusing core logic.

### User Authentication

The system has three primary user roles:
- **Admin**: Full access to create tournaments and manage players
- **Player**: Can create tournaments and record scores
- **Spectator**: View-only access to tournaments and results

## Key Workflows

1. **Tournament Creation**
   - Select tournament type (pairs or individual)
   - Select players or create pairs
   - Tournament structure (rounds, courts) calculated automatically

2. **Match Scoring**
   - Scores recorded per matchup with multiple sets
   - Point differences calculated automatically
   - Player rankings updated in real-time

3. **Tournament Management**
   - View matchups by round and court
   - Track player performance and rankings
   - Log history of match result changes
