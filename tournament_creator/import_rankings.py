import os
from django.db import transaction
from tournament_creator.models import Player

def import_rankings(filepath, dry_run=False):
    """
    Imports players from a rankings file. Each line: ranking<TAB>name<TAB>ranking_points
    If dry_run is True, print what would be imported but don't save to DB.
    """
    if not os.path.isfile(filepath):
        print(f"File not found: {filepath}")
        return

    to_create = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, 1):
            raw = line.strip().split('\t')
            if len(raw) != 3:
                print(f"Skipping line {line_no}: bad format: {line.strip()}")
                continue
            ranking, name, ranking_points = raw
            try:
                ranking = int(ranking)
                ranking_points = float(ranking_points)
                first_name, *rest = name.split(' ', 1)
                last_name = rest[0] if rest else ''
            except Exception as exc:
                print(f"Skipping line {line_no}: {exc}")
                continue
            player = Player(
                first_name=first_name,
                last_name=last_name,
                ranking=ranking
            )
            # If you add a ranking_points field to Player, set it here
            setattr(player, 'ranking_points', ranking_points)
            to_create.append(player)

    print(f"Will import {len(to_create)} players.")
    if dry_run:
        for p in to_create:
            print(f"{p.ranking}: {p.first_name} {p.last_name} ({getattr(p, 'ranking_points', '')} pts)")
    else:
        with transaction.atomic():
            Player.objects.bulk_create(to_create)
        print(f"Imported {len(to_create)} players.")
