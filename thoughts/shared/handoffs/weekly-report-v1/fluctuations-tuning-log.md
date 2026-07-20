# Fluctuations tuning log (NA 2026-07-06)

_Checkpoints to compare each threshold/logic change._

## Step 1 — paid Google-Search decomposition (CVR×AOV×TR)
NA 2026-07-06 · fluctuations: cvr=10 rpc=6 cm1=8 · down=15
| CE | signal | alert | mag% | dominant |
|---|---|---|---|---|
| Disneyland Resort California | cm1_per_conv | sustained_3d | -41.2 | CVR |
| Steamboat Natchez Tours | cm1_per_conv | sustained_3d | -31.9 | CVR |
| World of Coca-Cola | cm1_per_conv | sustained_3d | 41.9 |  |
| Hawaii Luaus | cm1_per_conv | sdlw | 73.6 |  |
| High Roller Observation Whee | cm1_per_conv | sustained_3d | 74.9 |  |
| Kennedy Space Center | cm1_per_conv | sustained_3d | 93.4 |  |
| Cruises - San Francisco | cm1_per_conv | sustained_3d | 105.5 |  |
| Canada's Wonderland Tickets | cm1_per_conv | sustained_3d | 122.6 |  |
| Six Flags Fiesta Texas Ticke | cvr | wow | -50.4 | CVR |
| Statue of Liberty | cvr | wow | -47.2 | CVR |
| Star of Honolulu | cvr | wow | -42.2 | CVR |
| New England Aquarium | cvr | wow | -41.9 | CVR |
| Kings Island Tickets | cvr | wow | -39.4 | CVR |
| Discovery Cove Orlando | cvr | wow | -39.3 | CVR |
| Seattle Whale Watching Tours | cvr | wow | -36.7 | CVR |
| LEGOLAND Florida | cvr | wow | -36.1 | CVR |
| Six Flags: Magic Mountain | cvr | wow | -33.8 | CVR |
| Museum of Modern Art (MoMA) | cvr | wow | -31.6 | CVR |
| Niagara Falls (Canada) Tours | rpc | sustained_3d | -41.0 | AOV |
| Boston Whale Watching Cruise | rpc | sustained_3d | -38.3 | CVR |
| Las Vegas Shows | rpc | sustained_3d | -23.1 | AOV |
| Cruises - Chicago | rpc | sustained_3d | 38.8 |  |
| Alcatraz Tours | rpc | sustained_3d | 64.9 |  |
| LEGOLAND New York | rpc | sustained_3d | 78.4 |  |

## Step 2 — 3-day persistence 20% → 25%
NA 2026-07-06 · fluctuations: cvr=10 rpc=6 cm1=6 · down=15
| CE | signal | alert | mag% |
|---|---|---|---|
| Disneyland Resort California | cm1_per_conv | sustained_3d | -41.2 |
| World of Coca-Cola | cm1_per_conv | sustained_3d | 41.9 |
| High Roller Observation Whee | cm1_per_conv | sustained_3d | 74.9 |
| Kennedy Space Center | cm1_per_conv | sustained_3d | 93.4 |
| Cruises - San Francisco | cm1_per_conv | sustained_3d | 105.5 |
| Canada's Wonderland Tickets | cm1_per_conv | sustained_3d | 122.6 |
| Six Flags Fiesta Texas Ticke | cvr | wow | -50.4 |
| Statue of Liberty | cvr | wow | -47.2 |
| Star of Honolulu | cvr | wow | -42.2 |
| New England Aquarium | cvr | wow | -41.9 |
| Kings Island Tickets | cvr | wow | -39.4 |
| Discovery Cove Orlando | cvr | wow | -39.3 |
| Seattle Whale Watching Tours | cvr | wow | -36.7 |
| LEGOLAND Florida | cvr | wow | -36.1 |
| Six Flags: Magic Mountain | cvr | wow | -33.8 |
| Museum of Modern Art (MoMA) | cvr | wow | -31.6 |
| Steamboat Natchez Tours | rpc | sustained_3d | -49.8 |
| Niagara Falls (Canada) Tours | rpc | sustained_3d | -41.0 |
| Boston Whale Watching Cruise | rpc | sustained_3d | -38.3 |
| Las Vegas Shows | rpc | sustained_3d | -23.1 |
| Alcatraz Tours | rpc | sustained_3d | 64.9 |
| LEGOLAND New York | rpc | sustained_3d | 78.4 |

## Step 3 — fct_orders 4-driver + multi-metric gate
NA 2026-07-06 · down-swings after gate = 7 (was 15). Decomposition = CVR×AOV×Completion×Take-rate, all Google-Search paid, orders from fct_orders. Gate: 1 red→≥25% (CVR≥30) · ≥2 red→collective RPC≤−20% · red-floor 15% · CM1/conv exempt.
| CE | alert | dominant | CVRΔ | AOVΔ | CRΔ | TRΔ |
|---|---|---|---|---|---|---|
| Discovery Cove Orlando | WoW | AOV | -23 | -33 | -3 | 4 |
| Disneyland Resort Californ | 3D | CVR | -23 | 8 | 1 | -2 |
| Kings Island Tickets | WoW | Take rate | -27 | -21 | 0 | -30 |
| LEGOLAND Florida | WoW | CVR | -40 | 15 | 0 | -2 |
| Six Flags Fiesta Texas Tic | WoW | CVR | -50 | 6 | 0 | -9 |
| Star of Honolulu | WoW | CVR | -41 | -26 | 26 | 6 |
| Statue of Liberty | WoW | CVR | -40 | 5 | -4 | 15 |
