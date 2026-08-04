import streamlit as st
import pandas as pd
import pulp
from sqlalchemy import create_engine

st.set_page_config(page_title="NIFL Fantasy Optimizer", layout="wide")

st.title("🏆 Irish League Fantasy Optimizer")
st.markdown("Generate up to 10 mathematically optimal lineups with strict diversity constraints.")

# ---------------------------------------------------------
# 1. FETCH DATA FROM POSTGRESQL
# ---------------------------------------------------------
@st.cache_data
def load_data():
    # Pulls the password securely from the vault
    db_uri = st.secrets["DB_URI"]
    engine = create_engine(db_uri)
    df = pd.read_sql("SELECT * FROM players", engine)
    
    # Create a display name (e.g., "John Doe (GLEN)") for the dropdown menus
    df['display_name'] = df['name'] + ' (' + df['club'] + ')'
    return df

df = load_data()

# ---------------------------------------------------------
# 2. SIDEBAR: SETTINGS & PREFERENCES
# ---------------------------------------------------------
st.sidebar.header("⚙️ Optimizer Settings")

# Feature: Custom Projections Upload
st.sidebar.subheader("1. Projections File")

# Clickable instructions dropdown
with st.sidebar.expander("ℹ️ How to format your CSV"):
    st.markdown("""
    Your file must be a `.csv` with exactly two column headers:
    1. `name` (Must match the database exactly)
    2. `projected_points` (Numbers only)
    
    **Example:**
    ```csv
    name,projected_points
    Joe Gormley,12.5
    Jordan Stewart,8.0
    ```
    *Note: You only need to include the players you want to change. Anyone missing from your file will automatically use the default points.*
    """)

uploaded_file = st.sidebar.file_uploader("Upload Projections", type=['csv'])

if uploaded_file is not None:
    proj_df = pd.read_csv(uploaded_file)
    df = df.merge(proj_df[['name', 'projected_points']], on='name', how='left')
    df['projected_points'] = df['projected_points'].fillna(df['wage'] * 0.15)
    st.sidebar.success("✅ Custom Projections Loaded!")
else:
    df['projected_points'] = df['wage'] * 0.15
    st.sidebar.info("Using default projected points (Wage * 0.15).")


# Feature: Force & Exclude Players
st.sidebar.subheader("2. Player Preferences")
player_options = sorted(df['display_name'].tolist())

forced_players = st.sidebar.multiselect(
    "Force Include (Max 4):",
    options=player_options,
    max_selections=4
)

excluded_players = st.sidebar.multiselect(
    "Exclude Players:",
    options=[p for p in player_options if p not in forced_players]
)

# Feature: Multi-Lineup Settings
st.sidebar.subheader("3. Lineup Generation")
num_lineups = st.sidebar.slider("Number of Lineups", min_value=1, max_value=10, value=3)
min_difference = st.sidebar.slider("Min. Different Players per Lineup", min_value=1, max_value=3, value=2)

with st.expander("📊 View Master Player Database"):
    st.dataframe(df[['position', 'name', 'club', 'wage', 'projected_points']], use_container_width=True)

# ---------------------------------------------------------
# 3. RUN OPTIMIZER BUTTON
# ---------------------------------------------------------
if st.button("🚀 Generate Optimal Squads", type="primary"):
    
    with st.spinner(f"Crunching the numbers for {num_lineups} lineups..."):
        
        # Initialize the base model
        model = pulp.LpProblem("Irish_League_Optimizer", pulp.LpMaximize)
        player_vars = pulp.LpVariable.dicts("Player", df['player_id'], cat='Binary')

        # Objective Function
        model += pulp.lpSum([df.loc[df['player_id'] == i, 'projected_points'].values[0] * player_vars[i] for i in df['player_id']])

        # Apply Force / Exclude Preferences
        forced_ids = df[df['display_name'].isin(forced_players)]['player_id'].tolist()
        excluded_ids = df[df['display_name'].isin(excluded_players)]['player_id'].tolist()

        for fid in forced_ids:
            model += player_vars[fid] == 1 
            
        for eid in excluded_ids:
            model += player_vars[eid] == 0 

        # Apply Rulebook Constraints
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
        # 4. SOLVE LOOP FOR MULTIPLE LINEUPS
        # ---------------------------------------------------------
        generated_squads = []

        for step in range(num_lineups):
            model.solve(pulp.PULP_CBC_CMD(msg=False)) # Suppress console output for speed
            
            if pulp.LpStatus[model.status] != 'Optimal':
                if step == 0:
                    st.error("🚨 No valid squad could be found! Try freeing up budget by changing your forced players.")
                else:
                    st.warning(f"Could only generate {step} lineups. Try reducing your strict preferences to find more combinations.")
                break

            # Extract the drafted players
            current_lineup_ids = []
            selected_players = []
            total_cost = 0
            total_points = 0

            for i in df['player_id']:
                if player_vars[i].varValue == 1.0:
                    current_lineup_ids.append(i)
                    player_row = df.loc[df['player_id'] == i].iloc[0]
                    selected_players.append(player_row)
                    total_cost += player_row['wage']
                    total_points += player_row['projected_points']
            
            # Save the lineup details
            generated_squads.append({
                "lineup_num": step + 1,
                "cost": total_cost,
                "points": total_points,
                "players": pd.DataFrame(selected_players)[['position', 'name', 'club', 'wage', 'projected_points']]
            })

            # Add the Overlap Constraint for the NEXT iteration
            # Max allowed overlap = (12 total players) - (min_difference)
            max_overlap = 12 - min_difference
            model += pulp.lpSum([player_vars[i] for i in current_lineup_ids]) <= max_overlap

        # ---------------------------------------------------------
        # 5. DISPLAY THE RESULTS USING TABS
        # ---------------------------------------------------------
        if generated_squads:
            st.success(f"✅ Successfully generated {len(generated_squads)} optimal lineups!")
            
            # Create a tab structure for easy browsing
            tabs = st.tabs([f"Lineup {squad['lineup_num']}" for squad in generated_squads])
            
            for index, tab in enumerate(tabs):
                with tab:
                    squad = generated_squads[index]
                    st.markdown(f"**Total Cost:** £{squad['cost']} | **Projected Points:** {squad['points']:.2f}")
                    st.table(squad['players'])