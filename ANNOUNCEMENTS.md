# Announcement drafts

## Discord

```text
Task 4 controlled review is done, and it made things worse.

Task 4 (extreme probe) results:
- DS4 solo: reward 0.0, F2P 20/22, P2P 58/58, 84m 31s wall, $0.379 recorded
- DS4 → K3 review → DS4 repair: reward 0.0, F2P 19/22, P2P 58/58, 89m 12s wall, $1.512 inferred comparison

The K3 review was genuinely substantive (it found a real frame-ordering bug, a memory-count mismatch, and a dangling-pointer risk), but the two solo misses survived and one additional check failed. The repair pass rewrote exactly the memory-collection paths behind the new failure. Review + one repair did not recover the first DS4 miss.

The lower recorded cost ($0.345 vs $0.379) is an accounting artifact: K3 roles are recorded at $0 by the gateway. At list price the route is about 4x the solo cost.

Next run: Task 4 K3 solo — does the failure belong to DS4 or to the task?

Task identities and fixtures stay private until each task closes.

Approach, sanitized aggregate data, harness code, and caveats:
https://github.com/bnivanov/omp-model-bench
```

## X

199 characters:

```text
Task 4 review made it worse: 19/22 F2P vs 20/22 solo, 89m, ~$1.51 vs $0.38. K3 review + one DS4 repair failed to recover the first DS4 miss. Next: K3 solo. https://github.com/bnivanov/omp-model-bench
```
