"""
League scheduling: place a league's matches into the time slots its players
are available for.

Pure Python + OR-Tools CP-SAT, no Django, so it can be tested with plain data.
The views build ``Slot``/``Match`` lists from the database and write the
result back (see ``views/signup_views.py``).

Hard rules:
  - every player of a match is available in its slot
  - nobody plays two matches in the same slot
  - a slot has at most ``courts`` matches
  - nobody plays more than ``max_per_day`` matches a day (if set)
  - nobody plays in two consecutive slots of a day (unless ``allow_back_to_back``)

Goals, in strict priority order (each solved to optimality before the next):
  1. schedule as many matches as possible
  2. if ``avoid_parallel``: as few matches alongside another one as possible,
     so a single court stays in use and the others stay free for pickup games
  3. follow the seeded schedule: each match is played about as far into the
     season as its round is into the seeded schedule. The seeded schedules put
     the toughest matches in the last rounds, so this keeps them last (and
     spreads the matches over the season).
"""
from dataclasses import dataclass, field
from datetime import date, time
from itertools import combinations, count

# Per-stage time limit (three stages at most, within gunicorn's 30 s request
# timeout). A 45-match league solves to optimality in a second or two; larger
# ones (double round robins) settle for the best schedule found in time.
STAGE_TIME_LIMIT = 6.0
# Integer scale of the seeding cost (CP-SAT needs integer coefficients)
SEEDING_SCALE = 1000


@dataclass(frozen=True)
class Slot:
    id: int
    date: date
    time: time


@dataclass(frozen=True)
class Match:
    id: int
    players: frozenset
    # Position in the seeded schedule: (stage, round); later rounds come later.
    order: tuple


@dataclass(frozen=True)
class FixedMatch:
    """A match that keeps its slot (already played); it still takes up a court
    and counts towards its players' matches that day."""
    players: frozenset
    slot_id: int
    court: int = 0


@dataclass
class ScheduleResult:
    # match id -> (slot id, court number starting at 1)
    assignments: dict = field(default_factory=dict)
    unscheduled: list = field(default_factory=list)
    parallel_matches: int = 0
    inversions: int = 0
    optimal: bool = True


def schedule_league(matches, slots, availability, courts=1, max_per_day=None,
                    allow_back_to_back=True, avoid_parallel=False, fixed=()):
    """
    ``availability`` maps player id -> set of slot ids. ``fixed`` are matches that
    keep their slot. Returns a ``ScheduleResult``; matches that fit no slot are
    listed in ``unscheduled`` rather than failing the whole schedule.
    """
    from ortools.sat.python import cp_model

    slots = sorted(slots, key=lambda s: (s.date, s.time, s.id))
    index = {s.id: i for i, s in enumerate(slots)}
    by_id = {s.id: s for s in slots}
    matches = sorted(matches, key=lambda m: (m.order, m.id))
    result = ScheduleResult()
    if not matches:
        return result

    fixed_load = {}
    fixed_courts = {}
    fixed_by_player = {}
    for f in fixed:
        if f.slot_id not in index:
            continue
        fixed_load[f.slot_id] = fixed_load.get(f.slot_id, 0) + 1
        fixed_courts.setdefault(f.slot_id, set()).add(f.court)
        for p in f.players:
            fixed_by_player.setdefault(p, set()).add(f.slot_id)

    def free_courts(slot_id):
        return courts - fixed_load.get(slot_id, 0)

    model = cp_model.CpModel()
    x = {}  # (match id, slot id) -> placed there
    for m in matches:
        busy = set().union(*(fixed_by_player.get(p, set()) for p in m.players))
        for s in slots:
            if (free_courts(s.id) > 0 and s.id not in busy
                    and all(s.id in availability.get(p, ()) for p in m.players)):
                x[m.id, s.id] = model.NewBoolVar(f'x_{m.id}_{s.id}')

    slots_of = {m.id: [s.id for s in slots if (m.id, s.id) in x] for m in matches}
    scheduled = {}
    for m in matches:
        scheduled[m.id] = model.NewBoolVar(f'scheduled_{m.id}')
        model.Add(sum(x[m.id, s] for s in slots_of[m.id]) == scheduled[m.id])

    # Court capacity
    for s in slots:
        placed = [x[m.id, s.id] for m in matches if (m.id, s.id) in x]
        if placed:
            model.Add(sum(placed) <= free_courts(s.id))

    # Per player: one match per slot, matches per day, back-to-back
    players = set().union(*(m.players for m in matches))
    days = {}
    for s in slots:
        days.setdefault(s.date, []).append(s.id)
    for p in players:
        mine = [m for m in matches if p in m.players]
        fixed_mine = fixed_by_player.get(p, set())

        def occupancy(slot_id):
            return [x[m.id, slot_id] for m in mine if (m.id, slot_id) in x]

        for s in slots:
            occ = occupancy(s.id)
            if len(occ) > 1:
                model.Add(sum(occ) <= 1)
        for day_slots in days.values():
            if max_per_day:
                occ = [v for sid in day_slots for v in occupancy(sid)]
                already = sum(1 for sid in day_slots if sid in fixed_mine)
                if occ:
                    model.Add(sum(occ) <= max(0, max_per_day - already))
            if not allow_back_to_back:
                for a, b in zip(day_slots, day_slots[1:]):
                    occ_a, occ_b = occupancy(a), occupancy(b)
                    if a in fixed_mine and occ_b:
                        model.Add(sum(occ_b) == 0)
                    elif b in fixed_mine and occ_a:
                        model.Add(sum(occ_a) == 0)
                    elif occ_a and occ_b:
                        model.Add(sum(occ_a) + sum(occ_b) <= 1)

    # Goal 2: matches alongside another one (a slot's matches beyond its first)
    parallel_terms = []
    for s in slots:
        placed = [x[m.id, s.id] for m in matches if (m.id, s.id) in x]
        load = fixed_load.get(s.id, 0)
        if len(placed) + load > 1:
            extra = model.NewIntVar(0, courts, f'parallel_{s.id}')
            model.Add(extra >= sum(placed) + load - 1)
            parallel_terms.append(extra)

    # Goal 3: follow the seeded schedule. A match's place in the seeded order
    # (0 = first round, 1 = last) should match its slot's place in the season
    # (0 = first slot, 1 = last); the cost is the squared difference, so large
    # deviations cost more than several small ones. Being linear in the
    # placement variables, this solves far faster than counting inversions.
    orders = sorted({m.order for m in matches})
    rank = {o: (i / (len(orders) - 1) if len(orders) > 1 else 0.5) for i, o in enumerate(orders)}
    season = {s.id: (index[s.id] / (len(slots) - 1) if len(slots) > 1 else 0.5) for s in slots}
    seeding_cost = sum(
        round(SEEDING_SCALE * (rank[m.order] - season[s]) ** 2) * x[m.id, s]
        for m in matches for s in slots_of[m.id]
    )

    goals = [(sum(scheduled.values()), 'max')]
    if avoid_parallel and parallel_terms:
        goals.append((sum(parallel_terms), 'min'))
    goals.append((seeding_cost, 'min'))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = STAGE_TIME_LIMIT
    solver.parameters.num_workers = 8
    placed = None  # (match id, slot id) keys of the best solution so far
    for goal, sense in goals:
        if sense == 'max':
            model.Maximize(goal)
        else:
            model.Minimize(goal)
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # A timeout before any solution: keep the previous goal's solution
            result.optimal = False
            break
        if status != cp_model.OPTIMAL:
            result.optimal = False
        placed = {key for key, var in x.items() if solver.Value(var)}
        # Keep this goal's value while optimizing the next ones, and start from
        # the solution just found.
        value = round(solver.ObjectiveValue())
        model.Add(goal >= value if sense == 'max' else goal <= value)
        model.ClearHints()
        for key, var in x.items():
            model.AddHint(var, key in placed)
    placed = placed or set()

    taken = {sid: set(c) for sid, c in fixed_courts.items()}
    for m in matches:  # seeded order: earlier matches get the lower courts
        slot_id = next((s for s in slots_of[m.id] if (m.id, s) in placed), None)
        if slot_id is None:
            result.unscheduled.append(m.id)
            continue
        court = next(c for c in count(1) if c not in taken.setdefault(slot_id, set()))
        taken[slot_id].add(court)
        result.assignments[m.id] = (slot_id, court)
    load = dict(fixed_load)
    for slot_id, _court in result.assignments.values():
        load[slot_id] = load.get(slot_id, 0) + 1
    result.parallel_matches = sum(n - 1 for n in load.values() if n > 1)
    result.inversions = count_inversions(matches, result.assignments, index)
    return result


def count_inversions(matches, assignments, index):
    """Pairs of scheduled matches where a later round's match is played before an
    earlier round's one: how far the schedule strays from the seeded order."""
    placed = [(m.order, index[assignments[m.id][0]]) for m in matches if m.id in assignments]
    return sum(1 for (o1, t1), (o2, t2) in combinations(placed, 2)
               if (o1 < o2 and t1 > t2) or (o2 < o1 and t2 > t1))
