import pandas as pd
import numpy as np
import difflib
import re

print("⚙️ Generating Refined NIFL Player Projections...")

# ---------------------------------------------------------
# 1. LOAD DATASETS
# ---------------------------------------------------------
try:
    df_master = pd.read_csv('master_sunday_life.csv')
    df_history = pd.read_csv('historical_points.csv')
    df_squads = pd.read_csv('nifl_squad_numbers_26_27_clean.csv')
except FileNotFoundError as e:
    print(f"❌ Error loading files: {e}")
    print("Ensure 'master_sunday_life.csv', 'historical_points.csv', and 'nifl_squad_numbers_26_27_clean.csv' exist.")
    exit()

# Deduplicate inputs to prevent Cartesian product duplicates
df_master = df_master.drop_duplicates(subset=['name']).copy()
df_history = df_history.drop_duplicates(subset=['name']).copy()
df_squads = df_squads.drop_duplicates(subset=['name']).copy()

# ---------------------------------------------------------
# 2. NORMALIZED & FUZZY NAME MATCHING ENGINE
# ---------------------------------------------------------
def clean_name(s):
    if not isinstance(s, str):
        return ""
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)  # Remove hyphens, apostrophes, and special characters
    
    # Common NIFL name alias normalization map
    name_map = {
        "pat": "patrick",
        "danny": "daniel",
        "dan": "daniel",
        "micheal": "michael",
        "mike": "michael",
        "mickey": "michael",
        "chris": "christopher",
        "andy": "andrew",
        "alex": "alexander",
        "matt": "matthew",
        "benji": "benjamin",
        "ben": "benjamin",
        "jonny": "jonathan",
        "johnny": "jonathan"
    }
    parts = s.split()
    if parts and parts[0] in name_map:
        parts[0] = name_map[parts[0]]
    return " ".join(parts)

df_history['clean_name'] = df_history['name'].apply(clean_name)
df_squads['clean_name'] = df_squads['name'].apply(clean_name)

history_clean_list = df_history['clean_name'].tolist()
squads_clean_list = df_squads['clean_name'].tolist()

def get_matched_history_pts(master_name):
    c_name = clean_name(master_name)
    # 1. Direct normalized match
    match = df_history[df_history['clean_name'] == c_name]
    if not match.empty:
        return match['projected_points'].values[0]
    
    # 2. Fuzzy match
    close_matches = difflib.get_close_matches(c_name, history_clean_list, n=1, cutoff=0.78)
    if close_matches:
        matched_clean = close_matches[0]
        return df_history[df_history['clean_name'] == matched_clean]['projected_points'].values[0]
    
    return np.nan

def get_matched_squad_num(master_name):
    c_name = clean_name(master_name)
    match = df_squads[df_squads['clean_name'] == c_name]
    if not match.empty:
        return match['squad_number'].values[0]
    
    close_matches = difflib.get_close_matches(c_name, squads_clean_list, n=1, cutoff=0.78)
    if close_matches:
        matched_clean = close_matches[0]
        return df_squads[df_squads['clean_name'] == matched_clean]['squad_number'].values[0]
    
    return np.nan

df_master['historical_points'] = df_master['name'].apply(get_matched_history_pts)
df_master['squad_number'] = df_master['name'].apply(get_matched_squad_num)

# ---------------------------------------------------------
# 3. CALCULATE POSITIONAL WAGE MULTIPLIERS
# ---------------------------------------------------------
df_known = df_master.dropna(subset=['historical_points']).copy()
df_known['multiplier'] = df_known['historical_points'] / df_known['wage']

pos_multipliers = df_known.groupby('position')['multiplier'].mean().to_dict()
default_multiplier = 0.38

# ---------------------------------------------------------
# 4. DYNAMIC PROJECTION ENGINE
# ---------------------------------------------------------
def calculate_projection(row):
    wage = float(row['wage'])
    pos = row['position']
    hist_pts = row['historical_points']
    squad_num = row['squad_number']
    
    pos_mult = pos_multipliers.get(pos, default_multiplier)
    wage_implied_pts = wage * pos_mult
    
    # --- A. TIERED PERFORMANCE WEIGHTING ---
    if pd.notna(hist_pts):
        if hist_pts >= 120:
            # Superstar Tier: 85% Historical + 15% Wage Baseline
            base_proj = (0.85 * hist_pts) + (0.15 * wage_implied_pts)
        elif hist_pts >= 70:
            # High Performing Tier: 75% Historical + 25% Wage Baseline
            base_proj = (0.75 * hist_pts) + (0.25 * wage_implied_pts)
        elif hist_pts < 0:
            # Floor Correction for Negative Score Outliers
            base_proj = (0.30 * hist_pts) + (0.70 * wage_implied_pts)
        else:
            # Standard Returning Player: 60% Historical + 40% Wage Baseline
            base_proj = (0.60 * hist_pts) + (0.40 * wage_implied_pts)
    else:
        # Cold Start (New Player): 100% Wage Baseline
        base_proj = wage_implied_pts
        
    # --- B. SQUAD NUMBER BOOST ---
    boost = 1.0
    if pd.notna(squad_num):
        try:
            num = float(squad_num)
            if 1 <= num <= 11:
                boost = 1.15  # Key Starting XI Boost (+15%)
            elif 12 <= num <= 22:
                boost = 1.05  # Regular Squad Rotation Boost (+5%)
        except ValueError:
            pass
            
    final_proj = base_proj * boost
    return round(final_proj, 1)

df_master['projected_points'] = df_master.apply(calculate_projection, axis=1)

# ---------------------------------------------------------
# 5. CLEAN & EXPORT
# ---------------------------------------------------------
df_export = df_master[['name', 'projected_points']].drop_duplicates(subset=['name'])
df_export.to_csv('player_projections.csv', index=False)

print("✅ Success! 'player_projections.csv' generated cleanly without duplicates.")
print("-" * 65)
print(df_master[['name', 'position', 'wage', 'historical_points', 'squad_number', 'projected_points']]
      .dropna(subset=['historical_points'])
      .sort_values('projected_points', ascending=False)
      .head(15)
      .to_string(index=False))
print("-" * 65)