# Frozen product transport authority boundary

The canonical Formation product path separates transport from authority:

- a Formation-published GitHub Issue is zero-authority transport (`origin=FORMATION_PUBLISHED_REQUEST`, `authority=false`);
- the verified Human `ACCEPT`/`MODIFY`/`REJECT` comment is the sole authority event;
- frozen-contract execution must therefore validate the exact Formation transport binding without reclassifying the request Issue as direct-Human authority;
- the Human decision retains the complete direct-Human provenance gate;
- legacy non-Formation frozen contracts retain the historical direct-Human request + decision requirements.

The validator fails closed if transport provenance is missing, mismatched across contract/snapshot/result, gains authority, points at a different Issue, or the Human decision loses direct-Human provenance.
