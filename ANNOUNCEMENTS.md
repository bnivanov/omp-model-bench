# Announcement drafts

## Discord

```text
Task 1 of my three-task OMP model-routing benchmark is officially complete. I tested seven routes on the empirical Very Easy anchor to compare solo execution, plan-yolo, prewalk, live advising, independent review plus one repair, and combinations.

Aggregate outputs:
- DS4 solo: reward 1.0, F2P 23/23, P2P 122/122, 25m 09s, $0.1047 recorded
- K3 plan-yolo → DS4: reward 1.0, F2P 23/23, 36m 49s, $1.3395 estimated combined
- K3 prewalk → DS4: reward 0.0, partial 0.9931, F2P 22/23, 18m 51s, $0.6111 estimated combined
- DS4 + K3 advisor: reward 1.0, F2P 23/23, 1h 31m 50s, $10.3985 estimated combined; hit the frozen model deadline
- DS4 → K3 review → DS4 repair: reward 1.0, F2P 23/23, 46m 40s, $0.8096 estimated combined
- K3 plan-yolo → DS4 → K3 review → DS4 repair: reward 1.0, F2P 23/23, 47m 05s, $1.7015 estimated combined
- DS4 + Luna advisor: reward 1.0, F2P 23/23, 1h 31m 15s, $1.3179 recorded; hit the frozen model deadline

Every route passed P2P 122/122. The Task 1 finding is that DS4 solo dominated every other full-quality route on cost and time: no augmentation improved measured quality, while live advisors added the most latency and cost. Controlled review was much more operationally predictable than continuous advising.

Phase 1 is now `1/3` complete and frozen as a Very Easy → Medium → Very Hard complexity ladder. “Very Easy” is model-relative and empirical; the Medium and Very Hard tasks were selected before execution by structural review. Task identities and fixtures stay private until each run closes. K3 helper costs are official list-price estimates because the gateway recorded those roles at $0.

Approach, sanitized aggregate data, harness code, and caveats:
https://github.com/bnivanov/omp-model-bench
```

## X

243 characters:

```text
Task 1 of my 3-task OMP routing benchmark is complete. DS4 solo hit 23/23 F2P + 122/122 P2P in 25m for $0.105. Phase 1 is frozen as an empirical Very Easy → Medium → Very Hard ladder; Task 2 is next. https://github.com/bnivanov/omp-model-bench
```
