import pulp
import pandas as pd

def generate_lineups(df, formation, num_lineups, min_diff, forced_names, excluded_names):
    """
    Takes the player dataframe and user constraints, solves the MILP knapsack problem,
    and returns a list of dictionaries containing the optimal optimal lineups.
    """
    generated_squads = []
    error_message = None

    model = pulp.LpProblem("NIFL_Optimizer", pulp.LpMaximize)
    player_vars = pulp.LpVariable.dicts("Player", df['id'], cat='Binary')

    # SPEED OPTIMIZATION: Dictionary lookups
    wages = dict(zip(df['id'], df['wage']))
    points = dict(zip(df['id'], df['projected_points']))
    clubs = dict(zip(df['id'], df['club']))

    # Objective Function
    model += pulp.lpSum([points[i] * player_vars[i] for i in df['id']])

    # Apply Force Include / Exclude Constraints
    forced_ids = df[df['display_name'].isin(forced_names)]['id'].tolist()
    excluded_ids = df[df['display_name'].isin(excluded_names)]['id'].tolist()

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

    f_def, f_mid, f_fwd = map(int, formation.split('-'))
    model += pulp.lpSum([player_vars[i] for i in def_ids]) == f_def
    model += pulp.lpSum([player_vars[i] for i in mid_ids]) == f_mid
    model += pulp.lpSum([player_vars[i] for i in fwd_ids]) == f_fwd

    # SOLVE LOOP FOR MULTIPLE LINEUPS
    for step in range(num_lineups):
        model.solve(pulp.PULP_CBC_CMD(msg=False))
        
        if pulp.LpStatus[model.status] != 'Optimal':
            if step == 0:
                error_message = "🚨 Infeasible Setup! The math engine couldn't find a valid team. Try clearing forced players or picking a different formation."
            else:
                error_message = f"Generated {step} unique lineup(s). Relax constraint sliders to discover more combinations."
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
        model += pulp.lpSum([player_vars[i] for i in current_lineup_ids]) <= (12 - min_diff)

    return generated_squads, error_message