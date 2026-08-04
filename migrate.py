import pandas as pd
from sqlalchemy import create_engine

# 1. CONNECT TO LOCAL DATABASE (The Source)
# ---> REPLACE 'YourNewPassword' WITH YOUR LOCAL POSTGRES PASSWORD <---
local_uri = 'postgresql+psycopg2://postgres:spurs1@127.0.0.1:5432/NIFL_fantasy_football'
local_engine = create_engine(local_uri)

# 2. CONNECT TO NEON CLOUD (The Destination)
# This is your exact Neon string, already formatted for you!
neon_uri = 'postgresql+psycopg2://neondb_owner:npg_32quzAMhnLpc@ep-bold-scene-za3watur-pooler.c-2.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
neon_engine = create_engine(neon_uri)

try:
    # 3. Pull data from your laptop
    print("Pulling players from local database...")
    df = pd.read_sql("SELECT * FROM players", local_engine)
    print(f"✅ Found {len(df)} players locally.")

    # 4. Push data to the cloud
    print("Pushing players to Neon cloud database. Please wait...")
    df.to_sql('players', neon_engine, if_exists='append', index=False)
    print("🚀 Migration complete! Your cloud database is fully loaded.")

except Exception as e:
    print(f"An error occurred: {e}")