# Watch run evaluation: watch_1010-1110 (10:10-11:10, 13 ticks)

## Headline

- Looping/orbiting vehicles within 5 km: 8/8 rated HIGH, median 2 min after code could see it; 8/8 named in an operator alert.
- Fast close approaches: 1/3 rated HIGH, median 0 min after code could see it; 2/3 named in an operator alert.
- HIGH ratings not backed by a code rule: 0 of 9; operator alerts not backed: 3 of 14.
- Agent turns: 65 (0 rules fallbacks); code sent 2 invalid answers back for repair and capped 2 levels.
- Field-report judgments: 63 (13 contradicted, 33 unverifiable, 16 consistent, 1 irrelevant); 14 flagged as possible deception.

## Must-catch vehicles (code ground truth)

| Vehicle | Why (code) | Visible from | Rated HIGH | Delay | In an alert | Delay |
|---|---|---|---|---|---|---|
| T0035 | fixed_range_orbit at 1.7 km | 10:10 | 10:20 | 10 min | 10:20 | 10 min |
| T0120 | fixed_range_orbit at 3.5 km | 10:10 | 10:10 | 0 min | 10:20 | 10 min |
| T0146 | fixed_range_orbit at 1.6 km | 10:10 | 10:10 | 0 min | 10:10 | 0 min |
| T0181 | fixed_range_orbit at 1.9 km | 10:10 | 10:15 | 5 min | 10:15 | 5 min |
| T0043 | loops_around_base at 0.6 km | 10:15 | 10:15 | 0 min | 10:15 | 0 min |
| T0015 | fixed_range_orbit at 2.6 km | 10:40 | 10:45 | 5 min | 10:45 | 5 min |
| T0158 | loops_around_base at 0.7 km | 10:40 | 10:40 | 0 min | 10:40 | 0 min |
| T0179 | fixed_range_orbit at 1.7 km | 10:55 | 11:00 | 5 min | 11:00 | 5 min |
| T0109 | fast approach at 1.8 km, ETA 4 min | 10:30 | no | – | 10:30 | 0 min |
| T0003 | fast approach at 0.5 km, ETA 3 min | 11:05 | no | – | no | – |
| T0172 | fast approach at 0.9 km, ETA 3 min | 11:10 | 11:10 | 0 min | 11:10 | 0 min |

## Decisions no code rule backs

- HIGH: none
- Alert at 10:20: Güneybatıda altı araç toplandı; iki hızlı yaklaşım başladı
- Alert at 10:45: Dört araç güneyden eşgüdümlü hızlı yaklaşıyor
- Alert at 11:10: Dört araç batıdan grup halinde üsse yaklaşıyor

## Method

Ground truth is recomputed from the raw tracks at every tick with the same deterministic code the system uses (`behavior_class`, `level_ceiling`), not from anything the agents wrote. A vehicle is must-catch while it loops around or orbits the base within 5 km, or approaches fast enough that the ceiling's approach rule allows HIGH. 'Rated HIGH' is the first HIGH an agent gave (a watcher's raise still waiting for its confirming check counts: it is on the map). Delay = first HIGH (or alert) minus the first tick the rule held; watchers take turns over sectors, so a vehicle can wait a tick before its sector is checked. Vehicles within 1 km of the base may be HIGH by the ceiling but are not must-catch unless they approach fast (most are parked cars), so a HIGH for them alone counts as not backed.
