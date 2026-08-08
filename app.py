import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from optimizer import generate_lineups  # 👈 Look here! We import your engine.

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

    def get_default_projection(row):
        wage = float(row['wage'])
        if row['position'] == 'AM':
            return round(wage * 0.19, 1)
        return round(wage * 0.42, 1)

    df['projected_points'] = df.apply(get_default_projection, axis=1)

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

# Sort options by position, then alphabetically by CLUB, then by NAME
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
# 3. RUN OPTIMIZER & DISPLAY RESULTS
# ---------------------------------------------------------
if st.button("🚀 Generate Optimal Squads", type="primary"):
    
    with st.spinner(f"Crunching the numbers for {num_lineups} lineups..."):
        
        # 👈 We now call the isolated backend engine!
        generated_squads, error_msg = generate_lineups(
            df=df, 
            formation=selected_formation, 
            num_lineups=num_lineups, 
            min_diff=min_difference, 
            forced_names=forced_players, 
            excluded_names=excluded_players
        )

        # Handle UI errors passed back from the engine
        if error_msg:
            if not generated_squads:
                st.error(error_msg)
            else:
                st.warning(error_msg)

        # Display the UI results
        if generated_squads:
            st.success(f"✅ Successfully generated {len(generated_squads)} mathematically optimal lineup(s)!")
            tabs = st.tabs([f"Lineup {squad['lineup_num']}" for squad in generated_squads])
            
            for index, tab in enumerate(tabs):
                with tab:
                    squad = generated_squads[index]
                    
                    st.markdown(f"**Total Cost:** £{squad['cost']:.0f}k *(Bank: £{4000 - squad['cost']:.0f}k)* | **Projected Points:** {squad['points']:.1f}")
                    
                    # Positional Sorting
                    sort_order = ['GK', 'DEF', 'MID', 'FWD', 'AM']
                    squad_df = squad['players'].copy()
                    squad_df['position'] = pd.Categorical(squad_df['position'], categories=sort_order, ordered=True)
                    squad_df = squad_df.sort_values('position').reset_index(drop=True)
                    
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