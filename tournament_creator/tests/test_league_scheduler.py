"""Tests for the league scheduler (plain data, no database)."""
import random
from collections import Counter
from datetime import date, time, timedelta

from django.test import SimpleTestCase

from ..league_scheduler import FixedMatch, Match, Slot, schedule_league

DAY = date(2026, 10, 5)


def slots_on(days, hours, start_id=1):
    """Slots at ``hours`` o'clock on ``days`` consecutive weeks."""
    slots, next_id = [], start_id
    for week in range(days):
        for hour in hours:
            slots.append(Slot(next_id, DAY + timedelta(weeks=week), time(hour)))
            next_id += 1
    return slots


def pair_match(match_id, pair1, pair2, round_number):
    """A doubles match; pair n is players 2n and 2n+1."""
    return Match(match_id, frozenset({2 * pair1, 2 * pair1 + 1, 2 * pair2, 2 * pair2 + 1}), (1, round_number))


def round_robin(num_pairs):
    """Circle-method round robin: the seeded order of the formats, roughly."""
    seeds = list(range(1, num_pairs + 1))
    matches, match_id = [], 1
    for round_number in range(1, num_pairs):
        for i in range(num_pairs // 2):
            matches.append(pair_match(match_id, seeds[i], seeds[-1 - i], round_number))
            match_id += 1
        seeds = [seeds[0], seeds[-1]] + seeds[1:-1]
    return matches


def everyone_everywhere(matches, slots):
    players = set().union(*(m.players for m in matches))
    return {p: {s.id for s in slots} for p in players}


class HardRuleTests(SimpleTestCase):
    def assert_valid(self, result, matches, slots, availability, courts, max_per_day=None,
                     allow_back_to_back=True):
        by_id = {m.id: m for m in matches}
        slot_by_id = {s.id: s for s in slots}
        per_slot = Counter(slot for slot, _ in result.assignments.values())
        self.assertTrue(all(n <= courts for n in per_slot.values()))
        courts_used = Counter(result.assignments.values())
        self.assertTrue(all(n == 1 for n in courts_used.values()), "two matches on one court")
        busy = {}
        for match_id, (slot_id, court) in result.assignments.items():
            self.assertLessEqual(court, courts)
            for p in by_id[match_id].players:
                self.assertIn(slot_id, availability[p])
                busy.setdefault(p, []).append(slot_by_id[slot_id])
        for p, played in busy.items():
            self.assertEqual(len(played), len({s.id for s in played}), "player double-booked")
            per_day = Counter(s.date for s in played)
            if max_per_day:
                self.assertTrue(all(n <= max_per_day for n in per_day.values()))
            if not allow_back_to_back:
                day_slots = {}
                for s in sorted(slots, key=lambda s: (s.date, s.time)):
                    day_slots.setdefault(s.date, []).append(s.id)
                ids = {s.id for s in played}
                for day in day_slots.values():
                    for a, b in zip(day, day[1:]):
                        self.assertFalse(a in ids and b in ids, "back-to-back matches")

    def test_everything_fits(self):
        matches = round_robin(6)
        slots = slots_on(5, [18, 19, 20])
        availability = everyone_everywhere(matches, slots)
        result = schedule_league(matches, slots, availability, courts=2)
        self.assertEqual(result.unscheduled, [])
        self.assert_valid(result, matches, slots, availability, courts=2)

    def test_only_slots_every_player_can_make(self):
        matches = [pair_match(1, 1, 2, 1)]
        slots = slots_on(1, [18, 19, 20])
        # Pair 1's partners overlap only at 19; pair 2 can do 19 and 20
        availability = {2: {1, 2}, 3: {2, 3}, 4: {2, 3}, 5: {2, 3}}
        result = schedule_league(matches, slots, availability)
        self.assertEqual(result.assignments, {1: (2, 1)})

    def test_unplaceable_match_is_reported_not_fatal(self):
        matches = [pair_match(1, 1, 2, 1), pair_match(2, 3, 4, 1)]
        slots = slots_on(1, [18])
        availability = everyone_everywhere(matches, slots)
        availability[9] = set()  # pair 4's second player can't make it
        result = schedule_league(matches, slots, availability)
        self.assertEqual(result.unscheduled, [2])
        self.assertIn(1, result.assignments)

    def test_court_capacity(self):
        matches = round_robin(4)  # 6 matches
        slots = slots_on(1, [18])
        result = schedule_league(matches, slots, everyone_everywhere(matches, slots), courts=2)
        # A player plays once per slot, so only two disjoint matches fit
        self.assertEqual(len(result.assignments), 2)

    def test_max_matches_per_day(self):
        matches = round_robin(4)  # every pair plays 3 matches
        slots = slots_on(1, [17, 18, 19, 20, 21, 22])
        availability = everyone_everywhere(matches, slots)
        result = schedule_league(matches, slots, availability, courts=2, max_per_day=2)
        # 2 matches per pair per day: 4 pairs * 2 / 2 = 4 matches
        self.assertEqual(len(result.assignments), 4)
        self.assert_valid(result, matches, slots, availability, courts=2, max_per_day=2)

    def test_no_back_to_back(self):
        matches = round_robin(4)
        slots = slots_on(2, [18, 19, 20])
        availability = everyone_everywhere(matches, slots)
        result = schedule_league(matches, slots, availability, courts=2, allow_back_to_back=False)
        # Per day each pair can play at 18 and 20 only
        self.assertEqual(result.unscheduled, [])
        self.assert_valid(result, matches, slots, availability, courts=2, allow_back_to_back=False)

    def test_fixed_matches_keep_their_court_and_block_players(self):
        matches = [pair_match(2, 1, 3, 2), pair_match(3, 2, 4, 2)]
        slots = slots_on(1, [18, 19])
        availability = everyone_everywhere([pair_match(1, 1, 2, 1)] + matches, slots)
        fixed = [FixedMatch(frozenset({2, 3, 4, 5}), slot_id=1, court=1)]  # pairs 1 & 2 at 18
        result = schedule_league(matches, slots, availability, courts=2, fixed=fixed)
        self.assertEqual(result.unscheduled, [])
        self.assertEqual(result.assignments[2], (2, 1))
        self.assertEqual(result.assignments[3], (2, 2))

    def test_random_instances_keep_every_rule(self):
        rng = random.Random(7)
        for _ in range(5):
            matches = round_robin(rng.choice([4, 6, 8]))
            slots = slots_on(rng.randint(3, 6), [17, 18, 19, 20])
            players = set().union(*(m.players for m in matches))
            availability = {p: {s.id for s in slots if rng.random() < 0.7} for p in players}
            courts = rng.choice([1, 2, 3])
            max_per_day = rng.choice([None, 1, 2])
            back_to_back = rng.choice([True, False])
            result = schedule_league(matches, slots, availability, courts=courts, max_per_day=max_per_day,
                                     allow_back_to_back=back_to_back, avoid_parallel=rng.choice([True, False]))
            self.assertEqual(len(result.assignments) + len(result.unscheduled), len(matches))
            self.assert_valid(result, matches, slots, availability, courts, max_per_day, back_to_back)


class GoalTests(SimpleTestCase):
    def test_last_round_is_played_last(self):
        matches = round_robin(4)
        slots = slots_on(3, [18, 19])
        result = schedule_league(matches, slots, everyone_everywhere(matches, slots), courts=2)
        last_round = [m.id for m in matches if m.order == (1, 3)]
        last_slot_ids = {s.id for s in slots[-2:]}
        self.assertTrue(all(result.assignments[m][0] in last_slot_ids for m in last_round))
        self.assertEqual(result.inversions, 0)

    def test_seeded_order_when_availability_allows(self):
        matches = round_robin(6)  # 5 rounds of 3
        slots = slots_on(5, [19])
        result = schedule_league(matches, slots, everyone_everywhere(matches, slots), courts=3)
        for m in matches:
            slot_id, _ = result.assignments[m.id]
            self.assertEqual(slot_id, m.order[1], "round n should be played in week n")

    def test_avoid_parallel_beats_seeding(self):
        # Two rounds of two matches and four slots: seeding alone may play a round
        # in parallel; avoiding parallel matches uses one court throughout, at the
        # cost of some seeded order
        matches = round_robin(4)[:4]
        slots = slots_on(1, [17, 18, 19, 20])
        availability = everyone_everywhere(matches, slots)
        parallel = schedule_league(matches, slots, availability, courts=2)
        single = schedule_league(matches, slots, availability, courts=2, avoid_parallel=True)
        self.assertEqual(single.parallel_matches, 0)
        self.assertEqual({court for _, court in single.assignments.values()}, {1})
        self.assertEqual(single.unscheduled, [])
        self.assertLessEqual(parallel.inversions, single.inversions)

    def test_avoid_parallel_still_uses_second_court_as_last_resort(self):
        matches = round_robin(4)[:2]  # two disjoint matches
        slots = slots_on(1, [18])
        result = schedule_league(matches, slots, everyone_everywhere(matches, slots),
                                 courts=2, avoid_parallel=True)
        self.assertEqual(result.unscheduled, [])
        self.assertEqual(result.parallel_matches, 1)

    def test_avoid_parallel_ranks_below_scheduling_everything(self):
        matches = round_robin(4)  # 6 matches, 3 rounds
        slots = slots_on(1, [17, 18, 19])
        result = schedule_league(matches, slots, everyone_everywhere(matches, slots),
                                 courts=2, avoid_parallel=True)
        self.assertEqual(result.unscheduled, [])
        self.assertEqual(result.parallel_matches, 3)

    def test_moc_matches_need_all_four_players(self):
        matches = [Match(1, frozenset({1, 2, 3, 4}), (1, 1))]
        slots = slots_on(1, [18, 19])
        availability = {1: {1, 2}, 2: {1, 2}, 3: {2}, 4: {1, 2}}
        result = schedule_league(matches, slots, availability)
        self.assertEqual(result.assignments, {1: (2, 1)})
