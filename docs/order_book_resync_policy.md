# Order-Book Resynchronization Policy

A reconstructed book is considered unsafe when any of the following occurs:

1. Depth buffer overflows before snapshot synchronization.
2. First post-snapshot event does not bridge the expected next update ID.
3. Futures `pu` does not equal the previously applied `u`.
4. Spot-style update range does not contain the expected next update ID.
5. Local book becomes crossed.
6. Best bid or best ask disappears.
7. Snapshot fetch fails repeatedly.

When unsafe:

```text
RESYNC_REQUIRED
  ├─ stop emitting healthy ReconstructedBookEvent objects
  ├─ block downstream signal generation for this symbol
  ├─ request a fresh REST snapshot
  ├─ clear buffered stale events
  └─ restart synchronization
```

Execution and risk services must treat `is_sequence_healthy = false` as a hard rejection condition.
