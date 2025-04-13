        # MOC logic
        if hasattr(archetype, 'tournament_category') and archetype.tournament_category == 'MOC':
            moc_player_form = MoCPlayerSelectForm(request.POST)
            if moc_player_form.is_valid():
                players = moc_player_form.cleaned_data['players']
                tournament = self.get_form().save(commit=False)
                tournament.number_of_rounds = archetype.calculate_rounds(len(players))
                tournament.number_of_courts = archetype.calculate_courts(len(players))
                tournament.save()
                tournament.players.set(players)
                archetype.generate_matchups(tournament, players)
                messages.success(self.request, "Tournament created successfully!")
                return redirect('tournament_detail', pk=tournament.pk)
            else:
                # Re-render with errors
                context = self.get_context_data(object=None)
                context['archetype'] = archetype
                context['moc_player_form'] = moc_player_form
                return render(request, 'tournament_creator/tournament_create.html', context)
