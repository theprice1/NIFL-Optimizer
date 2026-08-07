import os
import streamlit as st
import pandas as pd
import pulp
from sqlalchemy import create_engine

st.set_page_config(page_title="NIFL Fantasy Optimizer", layout="wide")

st.title("🏆 Irish League Fantasy Optimizer")
st.markdown("Generate mathematically optimal lineups strictly following Sunday Life rulebook constraints.")

# ---------------------------------------------------------
# 1. FETCH DATA FROM POSTGRESQL & BUILD PROJECTIONS
# ---------------------------------------------------------
@st.cache_data
def load_data():
    db_uri = st.secrets["DB_URI"].replace("postgresql+psycopg2://", "postgresql://")
    engine = create_engine(db_uri)
    df = pd.read_sql("SELECT * FROM players", engine)
    
    # Format display name to emphasize the club for easier scanning
    df['display_name'] = '[' + df['position'] + '] ' + df['club'] + ' - ' + df['name']

    # Dynamic Projection Engine (Mimics 2025/26 Final Season Points)
    def get_default_projection(row):
        wage = float(row['wage'])
        if row['position'] == 'AM':
            return round(wage * 0.19, 1)
        return round(wage * 0.42, 1)

    df['projected_points'] = df.apply(get_default_projection, axis=1)

    # If a local custom CSV exists on disk, merge it automatically
    if os.path.exists('player_projections.csv'):
        try:
            proj_df = pd.read_csv('player_projections.csv')
            if 'name' in proj_df.columns and 'projected_points' in proj_df.columns:
                df = df.merge(proj_df[['name', 'projected_points']], on='name', how='left', suffixes=('', '_file'))
                df['projected_points'] = df['projected_points_file'].combine_first(df['projected_points'])
                df.drop(columns=['projected_points_file'], inplace=True)
        except Exception:
            pass

    return df

df = load_data()

# ---------------------------------------------------------
# 2. SIDEBAR: SETTINGS, CSV UPLOADER & PREFERENCES
# ---------------------------------------------------------
st.sidebar.header("⚙️ Optimizer Settings")

st.sidebar.subheader("1. Projections Input")
with st.sidebar.expander("ℹ️ How Custom Projections Work"):
    st.markdown("""
    By default, the optimizer projects scores using a **wage-multiplier engine** calibrated to last season's final points.
    
    If you wish to upload your own custom model output:
    1. Upload a `.csv` file with headers `name` and `projected_points`.
    2. Player names must match the database.
    3. Any unlisted player in your CSV will automatically fall back to the default multiplier.
    """)

uploaded_file = st.sidebar.file_uploader("Upload Projections CSV", type=['csv'])

if uploaded_file is not None:
    try:
        proj_df = pd.read_csv(uploaded_file)
        if 'name' in proj_df.columns and 'projected_points' in proj_df.columns:
            df = df.merge(proj_df[['name', 'projected_points']], on='name', how='left', suffixes=('', '_uploaded'))
            df['projected_points'] = df['projected_points_uploaded'].combine_first(df['projected_points'])
            df.drop(columns=['projected_points_uploaded'], inplace=True)
            st.sidebar.success("✅ Custom CSV Projections Loaded!")
        else:
            st.sidebar.error("CSV must contain 'name' and 'projected_points' columns.")
    except Exception as e:
        st.sidebar.error(f"Error loading CSV: {e}")

st.sidebar.subheader("2. Player Preferences")

# Sort options by position (GK -> DEF -> MID -> FWD -> AM), then alphabetically by CLUB, then by NAME
pos_order = ['GK', 'DEF', 'MID', 'FWD', 'AM']
df['pos_cat'] = pd.Categorical(df['position'], categories=pos_order, ordered=True)
df_sorted = df.sort_values(by=['pos_cat', 'club', 'name']).reset_index(drop=True)
player_options = df_sorted['display_name'].tolist()

forced_players = st.sidebar.multiselect("Force Include (Max 4):", options=player_options, max_selections=4)
excluded_players = st.sidebar.multiselect("Exclude Players:", options=[p for p in player_options if p not in forced_players])

st.sidebar.subheader("3. Formation & Multi-Lineup")
formation_options = ["4-4-2", "4-3-3", "4-5-1", "5-3-2", "5-4-1", "3-4-3"]
selected_formation = st.sidebar.selectbox("Formation", options=formation_options)

num_lineups = st.sidebar.slider("Number of Lineups", min_value=1, max_value=10, value=3)
min_difference = st.sidebar.slider("Min. Different Players per Lineup", min_value=1, max_value=3, value=2)

with st.expander("📊 View Master Player Database & Projections"):
    st.dataframe(df[['position', 'name', 'club', 'wage', 'projected_points']], width="stretch")

# ---------------------------------------------------------
# 3. RUN OPTIMIZER & PULP MODEL BUILDING
# ---------------------------------------------------------
if st.button("🚀 Generate Optimal Squads", type="primary"):
    
    with st.spinner(f"Crunching the numbers for {num_lineups} lineups..."):
        model = pulp.LpProblem("NIFL_Optimizer", pulp.LpMaximize)
        player_vars = pulp.LpVariable.dicts("Player", df['id'], cat='Binary')

        # SPEED OPTIMIZATION: Dictionary lookups instead of Pandas .loc
        wages = dict(zip(df['id'], df['wage']))
        points = dict(zip(df['id'], df['projected_points']))
        clubs = dict(zip(df['id'], df['club']))

        # Objective Function
        model += pulp.lpSum([points[i] * player_vars[i] for i in df['id']])

        # Apply Force Include / Exclude Constraints
        forced_ids = df[df['display_name'].isin(forced_players)]['id'].tolist()
        excluded_ids = df[df['display_name'].isin(excluded_players)]['id'].tolist()

        for fid in forced_ids: 
            model += player_vars[fid] == 1 
        for eid in excluded_ids: 
            model += player_vars[eid] == 0 

        # Roster Size & Budget Cap Constraints
        model += pulp.lpSum([wages[i] * player_vars[i] for i in df['id']]) <= 4000
        model += pulp.lpSum([player_vars[i] for i in df['id']]) == 12

        # SUNDAY LIFE RULE: Exactly 1 player per club
        for club in df['club'].unique():
            model += pulp.lpSum([player_vars[i] for i in df['id'] if clubs[i] == club]) == 1

        # Position Requirements
        gk_ids = df[df['position'] == 'GK']['id'].tolist()
        def_ids = df[df['position'] == 'DEF']['id'].tolist()
        mid_ids = df[df['position'] == 'MID']['id'].tolist()
        fwd_ids = df[df['position'] == 'FWD']['id'].tolist()
        am_ids = df[df['position'] == 'AM']['id'].tolist()

        model += pulp.lpSum([player_vars[i] for i in gk_ids]) == 1
        model += pulp.lpSum([player_vars[i] for i in am_ids]) == 1

        f_def, f_mid, f_fwd = map(int, selected_formation.split('-'))
        model += pulp.lpSum([player_vars[i] for i in def_ids]) == f_def
        model += pulp.lpSum([player_vars[i] for i in mid_ids]) == f_mid
        model += pulp.lpSum([player_vars[i] for i in fwd_ids]) == f_fwd

        # ---------------------------------------------------------
        # 4. SOLVE LOOP FOR MULTIPLE LINEUPS
        # ---------------------------------------------------------
        generated_squads = []

        for step in range(num_lineups):
            model.solve(pulp.PULP_CBC_CMD(msg=False))
            
            if pulp.LpStatus[model.status] != 'Optimal':
                if step == 0:
                    st.error("🚨 Infeasible Setup! The math engine couldn't find a valid team. Try clearing forced players or picking a different formation.")
                else:
                    st.warning(f"Generated {step} unique lineup(s). Relax constraint sliders to discover more combinations.")
                break

            current_lineup_ids = []
            selected_players = []
            total_cost = 0
            total_points = 0

            for i in df['id']:
                if player_vars[i].varValue == 1.0:
                    current_lineup_ids.append(i)
                    player_row = df.loc[df['id'] == i].iloc[0]
                    selected_players.append(player_row)
                    total_cost += player_row['wage']
                    total_points += player_row['projected_points']
            
            generated_squads.append({
                "lineup_num": step + 1,
                "cost": total_cost,
                "points": total_points,
                "players": pd.DataFrame(selected_players)[['position', 'name', 'club', 'wage', 'projected_points']]
            })

            # Diversity overlap constraint
            model += pulp.lpSum([player_vars[i] for i in current_lineup_ids]) <= (12 - min_difference)

        # ---------------------------------------------------------
        # 5. DISPLAY RESULTS
        # ---------------------------------------------------------
        if generated_squads:
            st.success(f"✅ Successfully generated {len(generated_squads)} mathematically optimal lineup(s)!")
            tabs = st.tabs([f"Lineup {squad['lineup_num']}" for squad in generated_squads])
            
            for index, tab in enumerate(tabs):
                with tab:
                    squad = generated_squads[index]
                    
                    # Remaining Budget Math
                    st.markdown(f"**Total Cost:** £{squad['cost']:.0f}k *(Bank: £{4000 - squad['cost']:.0f}k)* | **Projected Points:** {squad['points']:.1f}")
                    
                    # Positional Sorting (GK -> DEF -> MID -> FWD -> AM)
                    sort_order = ['GK', 'DEF', 'MID', 'FWD', 'AM']
                    squad_df = squad['players'].copy()
                    squad_df['position'] = pd.Categorical(squad_df['position'], categories=sort_order, ordered=True)
                    squad_df = squad_df.sort_values('position').reset_index(drop=True)
                    
                    # Highlight the Star Player (Highest Points)
                    def highlight_max_points(s):
                        is_max = s == s.max()
                        return ['background-color: rgba(46, 123, 50, 0.4)' if v else '' for v in is_max]
                    
                    st.dataframe(squad_df.style.apply(highlight_max_points, subset=['projected_points']), width="stretch")

                    # CSV Export Button
                    st.markdown("<br>", unsafe_allow_html=True)
                    csv_export = squad_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label=f"📥 Download Lineup {squad['lineup_num']} (CSV)",
                        data=csv_export,
                        file_name=f"sunday_life_lineup_{squad['lineup_num']}.csv",
                        mime="text/csv",
                    )