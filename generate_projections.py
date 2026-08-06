import pandas as pd
import numpy as np

print("⚙️ Building Blended Projections with Squad Number Boosts...")

# 1. Load your three local datasets
# Ensure historical points is saved as 'historical_points.csv' from the previous extraction
try:
    df_master = pd.read_csv('master_sunday_life.csv')
    df_history = pd.read_csv('historical_points.csv')
    df_squads = pd.read_csv('nifl_squad_numbers_26_27_clean.csv')
except FileNotFoundError as e:
    print(f"❌ Error loading files: {e}. Make sure all 3 CSVs are in the folder.")
    exit()

# 2. Merge datasets together using the player's name
# Rename historical points to avoid column naming confusion
df_history.rename(columns={'projected_points': 'historical_points'}, inplace=True)

df = df_master.merge(df_history[['name', 'historical_points']], on='name', how='left')
df = df.merge(df_squads[['name', 'squad_number']], on='name', how='left')

# 3. Calculate Positional Multipliers (from players WITH historical data)
# This gives us the average points per £1k wage for each position
df_known = df.dropna(subset=['historical_points']).copy()
df_known['multiplier'] = df_known['historical_points'] / df_known['wage']
pos_multipliers = df_known.groupby('position')['multiplier'].mean().to_dict()

# Fallback multiplier just in case a position is missing
default_multiplier = 0.35 

# 4. The Projection Engine
def calculate_projection(row):
    wage = row['wage']
    pos = row['position']
    hist_pts = row['historical_points']
    squad_num = row['squad_number']
    
    # Get the expected point return for this player's wage tier and position
    pos_mult = pos_multipliers.get(pos, default_multiplier)
    wage_implied_pts = wage * pos_mult
    
    # --- A. BLENDED FORMULA ---
    if pd.notna(hist_pts):
        # Existing Player: 60% Historical Reality + 40% Wage Market Expectation
        base_proj = (0.60 * hist_pts) + (0.40 * wage_implied_pts)
    else:
        # New Player / Cold Start: 100% Wage Market Expectation
        base_proj = wage_implied_pts
        
    # --- B. SQUAD NUMBER BOOST ---
    # Give a 15% projection boost to players wearing 1-11 (highly likely to start)
    boost = 1.0
    if pd.notna(squad_num):
        try:
            # Handle string conversions safely
            if 1 <= float(squad_num) <= 11:
                boost = 1.15
        except ValueError:
            pass # Ignore non-numeric squad numbers if any exist
            
    final_proj = base_proj * boost
    return round(final_proj, 1)

# Apply the engine to every player
df['projected_points'] = df.apply(calculate_projection, axis=1)

# 5. Export clean CSV for the Streamlit Optimizer
df_export = df[['name', 'projected_points']]
df_export.to_csv('player_projections.csv', index=False)

print("✅ Success! 'player_projections.csv' has been generated.")
print("-" * 50)
print(df[['name', 'historical_points', 'squad_number', 'projected_points']].head(15).to_string(index=False))
print("-" * 50)