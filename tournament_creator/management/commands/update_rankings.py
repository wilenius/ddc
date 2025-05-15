import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from tournament_creator.models import Player, RankingsUpdate

class Command(BaseCommand):
    help = 'Updates player rankings from doubledisccourt.com API'

    def add_arguments(self, parser):
        parser.add_argument('--division', type=str, default='O', help='Division to update (default: O)')
        parser.add_argument('--year', type=str, default='2025', help='Year for rankings (default: 2025)')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without making changes')

    def handle(self, *args, **options):
        division = options['division']
        year = options['year']
        dry_run = options['dry_run']
        
        self.stdout.write(f"Updating {division} division rankings for {year}...")
        
        # API endpoint details
        base_url = "https://doubledisccourt.com"
        rankings_endpoint = "/data/ddc.php"
        player_endpoint = "/data/ddc.php"
        operation_rankings = "get-rankings"
        operation_player = "load-player"
        
        headers = {
            'accept': '*/*',
            'referer': 'https://doubledisccourt.com/results/rankings.html',
            'user-agent': 'Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
            'x-requested-with': 'XMLHttpRequest'
        }
        
        rankings_params = {
            'op': operation_rankings,
            'year': year
        }
        
        player_params = {
            'op': operation_player
        }
        
        # Create a new rankings update record
        update_record = RankingsUpdate(
            division=division,
            successful=False  # Initially set to False, updated to True on success
        )
        
        try:
            # Fetch rankings data
            self.stdout.write("Fetching rankings data...")
            response_rankings = requests.get(
                base_url + rankings_endpoint, 
                params=rankings_params, 
                headers=headers
            )
            response_rankings.raise_for_status()
            rankings_data = response_rankings.json()
            
            # Fetch player data
            self.stdout.write("Fetching player data...")
            response_player = requests.get(
                base_url + player_endpoint, 
                params=player_params, 
                headers=headers
            )
            response_player.raise_for_status()
            player_data = response_player.json()
            
            # Create a dictionary for player lookup
            player_dict = {player['id']: player['name'] for player in player_data}
            
            # Filter rankings for requested division
            filtered_rankings = [
                ranking for ranking in rankings_data 
                if ranking['division'] == division
            ]
            
            # Prepare for database update
            to_create = []
            to_update = []
            existing_player_ids = set(Player.objects.values_list('id', flat=True))
            
            for ranking in filtered_rankings:
                player_id = ranking['player_id']
                player_name = player_dict.get(player_id, "Unknown")
                
                # Split name into first and last name
                name_parts = player_name.split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ''
                
                rank = int(ranking['rank'])
                points = float(ranking['points'])
                
                # Check if player exists
                try:
                    player = Player.objects.get(first_name=first_name, last_name=last_name)
                    # Update existing player
                    player.ranking = rank
                    player.ranking_points = points
                    to_update.append(player)
                except Player.DoesNotExist:
                    # Create new player
                    player = Player(
                        first_name=first_name,
                        last_name=last_name,
                        ranking=rank,
                        ranking_points=points
                    )
                    to_create.append(player)
            
            # Show summary if dry run
            if dry_run:
                self.stdout.write(f"Would create {len(to_create)} new players:")
                for p in to_create:
                    self.stdout.write(f"  {p.ranking}: {p.first_name} {p.last_name} ({p.ranking_points} pts)")
                
                self.stdout.write(f"Would update {len(to_update)} existing players:")
                for p in to_update:
                    self.stdout.write(f"  {p.ranking}: {p.first_name} {p.last_name} ({p.ranking_points} pts)")
            else:
                # Apply updates in a transaction
                with transaction.atomic():
                    # Create new players
                    if to_create:
                        Player.objects.bulk_create(to_create)
                        self.stdout.write(f"Created {len(to_create)} new players")
                    
                    # Update existing players
                    for player in to_update:
                        player.save()
                    
                    self.stdout.write(f"Updated {len(to_update)} existing players")
                    
                    # Update the rankings update record
                    update_record.player_count = len(to_create) + len(to_update)
                    update_record.successful = True
                    update_record.save()
            
            self.stdout.write(self.style.SUCCESS(f"Successfully processed {division} division rankings"))
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching data from API: {str(e)}"
            self.stderr.write(self.style.ERROR(error_msg))
            update_record.error_message = error_msg
            if not dry_run:
                update_record.save()
            raise CommandError(error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.stderr.write(self.style.ERROR(error_msg))
            update_record.error_message = error_msg
            if not dry_run:
                update_record.save()
            raise CommandError(error_msg)