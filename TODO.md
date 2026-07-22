# TODO

## Open

* Forfeits: no first-class support. For now, record a forfeit as a conventional
  score (e.g. 21–0 to the non-forfeiting pair, per the format), which yields the
  correct win/loss/PD. If a forfeit ends up mattering for a pool tie, the TD
  resolves it by hand with the "Resolve Tiebreaks" button (manual pool tiebreak
  resolution, step 7). This produces correct final standings; it is just not
  automatic — nothing flags a tie as forfeit-involved, so the TD has to notice.
  Deferred first-class plan (a `Matchup.forfeited_by` FK feeding tiebreak step 1,
  "fewest forfeits") was intentionally not done before European Open 2026 to
  avoid touching prod code right before the tournament.
* Make Euros format work for 11–40 pairs (currently only exactly 20 pairs; needs
  per-count pool layouts and an explicit format selector in the creation UI)

## Done

* ~~Implement multi-phase tournaments (e.g., round-robin + playoffs)~~ —
  multi-stage tournaments + Euros format (pools → pools → finals)
* ~~Recording didn't know final vs interim score / how many games~~ —
  `default_sets_per_match` on the tournament + warn-and-confirm score validation
  (`get_score_rules`)
* ~~Tournament-based rights management (only players + TD record scores)~~ —
  `user_can_edit_results`, per-tournament roles, past-tournament lock
* ~~Make notification messages look nicer~~ — compact, parseable match-result
  notifications
* ~~Tournament (phase) resolution view: show results, see if tiebreaks are
  resolved, or if TD is needed~~ — pool standings show how each tie was resolved,
  unresolved-seed-tie warning gates "Generate next phase"
* ~~Create a results report from a tournament~~ — download tournament results
* ~~Separate tie-break logic for single-player (MoC) tournaments, incl. Kodiak
  formats with uneven match counts~~ — MoC tiebreaks (`_apply_moc_tiebreaks`)
* ~~Player account registration (linked to ranking list data?)~~ — `Player.user`
  link + account registration
