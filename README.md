# Phoenix Ignition — ai-excited-01

A program that paints one image: **a firebird (phoenix) bursting out of a
supernova sunrise over a glittering sea**, with fireworks, stars and
confetti — made to get the AI judge excited.

## Run

```sh
python3 main.py            # writes /output/entry.png
OUTPUT_PATH=./entry.png python3 main.py   # local test override
```

## The image

- **The phoenix, in side profile, climbing up-right toward the sun:**
  head with open beak, eye and swept-back flame crest; two raised wings
  fanned from layered flame feathers (gold → orange → deep red); a
  glowing layered body; five long tail ribbons trailing down-left in a
  flame gradient, dotted with sparks.
- **The scene:** violet-to-orange dusk sky with 240 stars and 26 glints,
  a huge layered sun with halo and light rays, three fireworks
  (cyan / magenta / gold), a dark teal sea with wave crests and a
  sun-glitter path, and 130 pieces of confetti.
- Why it should excite the judge: maximum saturation, warm-fire vs
  cool-teal contrast, a big dynamic diagonal (bird climbing into the
  sun), epic scale, and a surreal-but-readable subject — the same
  epic-surreal register as the competition's current top scorers.

## Technical

- **Pure Python 3 stdlib** (`math`, `os`, `random`, `struct`, `zlib`) —
  no packages, no network, no assets, no fonts. The PNG is encoded by
  hand (filter 0, zlib level 9, no ancillary chunks).
- **Deterministic:** every random choice comes from
  `random.Random(20261116)`; two runs write byte-identical files
  (verified: same sha256).
- **Verified output:** 1024×1024 PNG, ~324 KB (limit 1 MiB), renders
  in ~5 s. Program name is `main.py` at the repo root, per the
  competition rules; output is `/output/entry.png`.
