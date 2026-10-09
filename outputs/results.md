# Results

> **DEMO DATA — these numbers prove the code runs, not a business claim.**
> Re-run without `--demo` on the real REES46 files before publishing any number.

Source: **Demo data (REES46 schema, simulated)** · cutoff 2019-11-01 · horizon 30 days · top-5

## Next-need prediction (backtest)

| Segment | Show what's popular | Predict next need | Lift | + mission boost |
|---|---|---|---|---|
| all customers | 30.0% | 59.0% | 1.97x | 58.8% |
| in a mission | 27.9% | 77.8% | 2.79x | 77.3% |
| no mission | 31.6% | 44.2% | 1.40x | 44.2% |

Purchase hit rate (next new need *bought* was in the top 5): popularity 17.8% vs next-need model 64.1%.
Customers evaluated: 4,439.

## Where customers are right now

- 41% of active customers show a life-mission pattern.
- Gone quiet: 29% of mission customers
- Next need: 29% of mission customers
- Ready to buy: 19% of mission customers
- Researching: 14% of mission customers
- Mission complete: 8% of mission customers
- Exploring: 1% of mission customers

Missions detected (primary):

- Setting up a new home: 1,354
- Building a home office: 1,192
- Preparing for a baby / growing family: 890
- Upgrading the kitchen: 814
- Starting an active lifestyle: 769
- Building a home entertainment setup: 595

## Wasted retargeting

- 7.2% of 'last 5 viewed' retargeting slots point at a product the customer already bought.
- 20.4% point at a need (e.g. 'a fridge') the customer already bought.

## Strongest next-need transitions

- computers.peripherals.printer → stationery.cartrige: 32% (n=124)
- sport.trainer → sport.tennis: 30% (n=128)
- electronics.video.projector → electronics.audio.music_tools: 30% (n=125)
- kids.dolls → kids.skates: 28% (n=141)
- appliances.kitchen.mixer → appliances.kitchen.juicer: 24% (n=131)

## Mission depth vs next-month behaviour (correlation, not causation)

- 0 - bought outside any mission: repeat rate 23%, avg next-month spend 91
- 1 need in mission: repeat rate 35%, avg next-month spend 101
- 2+ needs in mission: repeat rate 36%, avg next-month spend 103
