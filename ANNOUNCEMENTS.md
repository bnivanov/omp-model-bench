# Announcement drafts

## Discord

```text
I wrapped the preliminary Task 1 results from my OMP model-routing benchmark. I tested seven routes on the same coding task to compare where extra model intelligence pays off: solo execution, plan-yolo, prewalk, live advising, independent review plus one repair, and combinations.

Aggregate outputs:
- DS4 solo: reward 1.0, F2P 23/23, P2P 122/122, 25m 09s, $0.1047 recorded
- K3 plan-yolo → DS4: reward 1.0, F2P 23/23, 36m 49s, $1.3395 estimated combined
- K3 prewalk → DS4: reward 0.0, partial 0.9931, F2P 22/23, 18m 51s, $0.6111 estimated combined
- DS4 + K3 advisor: reward 1.0, F2P 23/23, 1h 31m 50s, $10.3985 estimated combined; hit the frozen model deadline
- DS4 → K3 review → DS4 repair: reward 1.0, F2P 23/23, 46m 40s, $0.8096 estimated combined
- K3 plan-yolo → DS4 → K3 review → DS4 repair: reward 1.0, F2P 23/23, 47m 05s, $1.7015 estimated combined
- DS4 + Luna advisor: reward 1.0, F2P 23/23, 1h 31m 15s, $1.3179 recorded; hit the frozen model deadline

Every route passed P2P 122/122. The preliminary takeaway is that DS4 solo dominated every other full-quality Task 1 route on cost and time: no augmentation improved measured quality, while live advisors added the most latency and cost. Controlled review was much more operationally predictable than continuous advising.

This is one task, so it is routing evidence rather than a universal model leaderboard. K3 helper costs are official list-price estimates because the gateway recorded those roles at $0.

Approach, sanitized aggregate data, harness code, and caveats:
https://github.com/bnivanov/omp-model-bench
```

## X

280 characters:

```text
Preliminary Task 1 results from my OMP routing benchmark (7 routes, 1 coding task): DS4 solo hit 23/23 F2P + 122/122 P2P in 25m for $0.105. Six routes hit full quality; solo dominated them on cost and time. Live advisors hit 90m limits. https://github.com/bnivanov/omp-model-bench
```
