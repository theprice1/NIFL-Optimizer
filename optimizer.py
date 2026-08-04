import pandas as pd
import pulp
from sqlalchemy import create_engine

# ---------------------------------------------------------
# 1. CONNECT TO POSTGRESQL & LOAD DATA
# ---------------------------------------------------------
# Replace 'YourNewPassword' with your actual database password
db_uri = 'postgresql+psycopg2://postgres:spurs1@127.0.0.1:5432/NIFL_fantasy_football'
engine = create_engine(db_uri)

df = pd.read_sql("SELECT * FROM players", engine)

# Mock 'projected_points' for pre-season testing
df['projected_points'] = df['wage'] * 0.15 

# ---------------------------------------------------------
# 2. INITIALIZE THE LINEAR PROGRAMMING MODEL
# ---------------------------------------------------------
model = pulp.LpProblem("Irish_League_Optimizer", pulp.LpMaximize)
player_vars = pulp.LpVariable.dicts("Player", df['player_id'], cat='Binary')

# ---------------------------------------------------------
# 3. SET THE OBJECTIVE FUNCTION
# ---------------------------------------------------------
model += pulp.lpSum([df.loc[df['player_id'] == i, 'projected_points'].values[0] * player_vars[i] for i in df['player_id']])

# ---------------------------------------------------------
# 4. APPLY THE RULEBOOK CONSTRAINTS
# ---------------------------------------------------------
model += pulp.lpSum([df.loc[df['player_id'] == i, 'wage'].values[0] * player_vars[i] for i in df['player_id']]) <= 4000
model += pulp.lpSum([player_vars[i] for i in df['player_id']]) == 12
model += pulp.lpSum([player_vars[i] for i in df['player_id'] if df.loc[df['player_id'] == i, 'position'].values[0] == 'AM']) == 1
model += pulp.lpSum([player_vars[i] for i in df['player_id'] if df.loc[df['player_id'] == i, 'position'].values[0] == 'GK']) == 1

def_vars = [player_vars[i] for i in df['player_id'] if df.loc[df['player_id'] == i, 'position'].values[0] == 'DEF']
mid_vars = [player_vars[i] for i in df['player_id'] if df.loc[df['player_id'] == i, 'position'].values[0] == 'MID']
fwd_vars = [player_vars[i] for i in df['player_id'] if df.loc[df['player_id'] == i, 'position'].values[0] == 'FWD']

model += pulp.lpSum(def_vars) >= 3
model += pulp.lpSum(def_vars) <= 5
model += pulp.lpSum(mid_vars) >= 3
model += pulp.lpSum(mid_vars) <= 5
model += pulp.lpSum(fwd_vars) >= 1
model += pulp.lpSum(fwd_vars) <= 3
model += pulp.lpSum(def_vars) + pulp.lpSum(mid_vars) + pulp.lpSum(fwd_vars) == 10 

clubs = df['club'].unique()
for club in clubs:
    model += pulp.lpSum([player_vars[i] for i in df['player_id'] if df.loc[df['player_id'] == i, 'club'].values[0] == club]) <= 1

# ---------------------------------------------------------
# 5. SOLVE AND OUTPUT THE SQUAD
# ---------------------------------------------------------
model.solve()

total_cost = 0
total_proj_points = 0

print("\n--- OPTIMAL SQUAD ---")
for i in df['player_id']:
    if player_vars[i].varValue == 1.0:
        player_row = df.loc[df['player_id'] == i].iloc[0]
        total_cost += player_row['wage']
        total_proj_points += player_row['projected_points']
        print(f"[{player_row['position']}] {player_row['name']} ({player_row['club']}) - £{player_row['wage']}")

print("---------------------")
print(f"Total Cost: £{total_cost}")
print(f"Projected Points: {total_proj_points:.2f}\n")