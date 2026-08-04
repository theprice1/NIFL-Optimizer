import pandas as pd
from sqlalchemy import create_engine

# 1. YOUR NEON CONNECTION STRING GOES HERE
# CRUCIAL: You must add '+psycopg2' immediately after the word 'postgresql'
neon_uri = 'postgresql+psycopg2://neondb_owner:npg_32quzAMhnLpc@ep-bold-scene-za3watur-pooler.c-2.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

# Create the engine to talk to Neon
engine = create_engine(neon_uri)

# 2. Read your perfect, duplicate-free CSV file from your hard drive
print("Reading local data...")
df = pd.read_csv('C:/fantasy_data/players.csv')

# 3. Push the data across the internet into the Neon 'players' table
print("Uploading 297 players to the cloud. Please wait...")
df.to_sql('players', engine, if_exists='append', index=False)

print("Cloud upload complete! 🚀")