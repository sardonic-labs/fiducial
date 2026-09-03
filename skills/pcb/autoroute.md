# Deterministic autoroute for non-spatial AI models

Non-spatial models (LLMs) cannot do geometry: they hallucinate coordinates,
lose the occupancy grid, and cannot close a DRC loop. Use the integrated
deterministic router — the AI declares *what* to connect, the router decides
*where*, byte-identically.

## When to use

* AI has produced a `.kicad_pcb` with footprints + nets (from `SchematicBuilder`
  or `kicad-cli`) and needs tracks without human routing.
* You need CI-repeatable routing: same input → same `segment`/`via` S-exprs,
  no randomness, no per-session Python maze (`pcb/layout.md:6`).

## Interface — AI is topological, router is geometric

```
intent.csv / placement.csv (AI)  →  autorouter  →  .kicad_pcb + (segment …) + (via …)
```

Agent never emits `(segment (start …)`. Agent ensures nets are correct
(`lint`/`check-intent`), then calls:

```
python fiducial/scripts/fiducial.py autoroute board.kicad_pcb --width 0.25 --grid 0.25 --strategy astar --json
python fiducial/scripts/fiducial.py autoroute board.kicad_pcb --out routed.kicad_pcb --dry-run --json
```

Exit: `0` routed, `1` unrouted ( JSON `unrouted:[{net,code,pads}]`), `2` env.

## Determinism contract

* Nets sorted by `(net_code)`; pads sorted by `(x,y,ref,pad)` — `pcb_router.py:1` `GRID_MM`.
* Grid `0.25 mm` snap (`_snap`), fixed neighbour order `+x,-x,+y,-y` in A*.
* `astar` = Manhattan maze + clearance `0.2 mm` obstacle grid from existing
  `segment`/`Edge.Cuts`; falls back to `escape` (L-route) if blocked.
* `escape` = one-bend L-route (`pcb/layout.md:11` lanes) — horizontal-first if
  `dx>=dy`, else vertical-first. No rip-up randomness, fixed 3-pass order.

## What it does

1. Parse `kicad_pcb` via `fiducial.py:20 parse_sexp`, pads via `pcb_router.py:51 _get_pads`,
   outline via `_get_outline` (`pcb_check.py:531`).
2. Group pads by net (`net 1 "GND"` → code 1). Allocate missing nets deterministically.
3. Skip nets already having a `segment` with that `net` code (idempotent).
4. For each unrouted net with ≥2 pads, chain pads sequentially with `astar` or `escape`,
   blocking occupied cells incrementally (`blocked` set) so later nets avoid earlier.
5. Emit `(segment (start x y) (end x y) (width w) (layer F.Cu) (net n) (uuid …))`
   — `pcb_router.py:110 _path_to_segments`, `uuid4`.
6. Append to board text before final `)` and write. Verify:

```
python fiducial/scripts/fiducial.py drc board.kicad_pcb --json
python fiducial/scripts/pcb_check.py trace-widths board.kicad_pcb
python fiducial/scripts/fiducial.py render board.kicad_pcb --outdir render
```

## Choosing a strategy

* `astar` (default) — maze, obstacle-aware, good for 2-layer dense boards.
* `escape` — explicit lanes, fastest, best when placement already lanes nets
  (e.g. connector breakout columns).

Both are deterministic; `astar` falls back to `escape` for start/goal blocked
cases (pad at origin).

## Example

```sh
# AI places 2 resistors sharing GND/VCC (net 1,2) on F.Cu, no tracks yet
python fiducial/scripts/fiducial.py autoroute demo.kicad_pcb --dry-run --json
# {"routed_nets":2,"segment_count":2,"via_count":0,"unrouted":[]}
python fiducial/scripts/fiducial.py autoroute demo.kicad_pcb --out routed.kicad_pcb
python fiducial/scripts/fiducial.py drc routed.kicad_pcb
```

## Verification

* Repeatability: `autoroute --dry-run` twice → identical JSON (`segment_count`,
  `routed_nets`).
* Idempotence: routing an already-routed board → `0` new segments.
* Fixture `tests/fixtures/healthy.kicad_pcb:1` — single-component board
  → `0` routed (no net with ≥2 pads).
* Multi-pad synthetic (R1+R2 on GND/VCC) → `2` nets, `2` segments, straight
  Manhattan.
