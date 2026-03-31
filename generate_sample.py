"""
Generate a realistic sample CDR dataset for demo purposes.
Run:  python generate_sample.py
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import os

random.seed(42)
np.random.seed(42)

# ── Phone number pool ─────────────────────────────────────────────────────────
# Simulated suspects, associates, and innocents
SUSPECTS = ["9876543210", "9123456789", "9000011111"]
ASSOCIATES = ["9988776655", "9112233445", "9765432100", "9345678901"]
INNOCENT = [f"9{random.randint(100000000, 999999999)}" for _ in range(20)]
ALL_NUMBERS = SUSPECTS + ASSOCIATES + INNOCENT

def random_phone(exclude=None):
    pool = [p for p in ALL_NUMBERS if p != exclude]
    return random.choice(pool)

# ── Generate records ──────────────────────────────────────────────────────────
records = []
base_date = datetime.now() - timedelta(days=45)

for i in range(600):
    dt = base_date + timedelta(
        days=random.randint(0, 44),
        hours=random.randint(6, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    # Weight suspect interactions more heavily
    if random.random() < 0.45:
        caller = random.choice(SUSPECTS)
        receiver = random.choice(SUSPECTS + ASSOCIATES) if random.random() < 0.6 else random_phone(caller)
    else:
        caller = random_phone()
        receiver = random_phone(caller)

    duration = max(5, int(np.random.exponential(90)))  # avg ~90s, min 5s
    records.append({
        "caller": caller,
        "receiver": receiver,
        "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "duration": duration,
    })

df = pd.DataFrame(records).sort_values("timestamp").reset_index(drop=True)

out_path = os.path.join(os.path.dirname(__file__), "sample_cdr.csv")
df.to_csv(out_path, index=False)
print(f"✅ Generated {len(df)} CDR records → {out_path}")
print(f"\nSuspect numbers in dataset:")
for s in SUSPECTS:
    cnt = ((df["caller"] == s) | (df["receiver"] == s)).sum()
    print(f"  {s}  →  {cnt} call appearances")
print("\nSample queries to try:")
print(f'  "Show calls from {SUSPECTS[0]} last month"')
print(f'  "Calls between {SUSPECTS[0]} and {SUSPECTS[1]}"')
print(f'  "All calls longer than 200 seconds last month"')
print(f'  "Calls from {SUSPECTS[2]} after 2024-01-01"')
