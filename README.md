# 🏆 NIFL Fantasy Football Optimizer

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B)
![PuLP](https://img.shields.io/badge/PuLP-Optimization-brightgreen)
![Pandas](https://img.shields.io/badge/Pandas-Data%20Science-150458)

A mathematical optimization engine and interactive dashboard built to generate the perfect fantasy football lineup for the Sunday Life NIFL (Northern Ireland Football League) Fantasy Football game.

Instead of relying on gut feeling, this project treats squad selection as a strict knapsack optimization problem. It uses Mixed Integer Linear Programming (MILP) to find the absolute maximum projected points possible while strictly adhering to complex budget and roster constraints.

## 🧠 The Problem (Sunday Life Constraints)

Building a valid team in this specific fantasy format requires balancing a rigid set of rules:

- **Total Budget:** £4,000k max.
- **Squad Size:** Exactly 12 players.
- **Club Limit:** Exactly 1 player from each of the 12 NIFL Premiership clubs.
- **Positions:** 1 Goalkeeper, 1 Assistant Manager, and a valid outfield formation.

## 🚀 Key Features

- **Mathematical Optimization Engine:** Solves the constrained optimization problem in milliseconds using PuLP.
- **Dynamic Projection Pipeline:** Evaluates returning veterans and newly signed players using a weighted algorithm.
  - *Elite Performers:* 85/15 split favoring historical point totals.
  - *Cold Starts:* Imputes projected points based on wage and positional market value.
  - *Contextual Adjustments:* Applies a 15 percent probability boost for numbers 1 to 11.
- **Fuzzy Logic Data Merging:** Utilizes difflib and string normalization to seamlessly merge messy data.
- **Diversity Lineup Generator:** Iteratively solves for sub-optimal lineups by enforcing an overlap constraint.
- **Interactive Dashboard:** A clean UI for forcing or excluding specific players, tracking budgets, and exporting.

## 📐 Mathematical Formulation

The optimization is framed as a binary integer programming problem. Let $x_i \in \{0, 1\}$ represent the decision to include player $i$ in the squad.

**Objective Function:**

Maximize total projected points:

$$\max \sum_{i=1}^{n} (Points_i \times x_i)$$

**Subject to Constraints:**

1. **Budget Cap:**

   $$\sum_{i=1}^{n} (Wage_i \times x_i) \le 4000$$

2. **Roster Size:**

   $$\sum_{i=1}^{n} x_i = 12$$

3. **Club Distribution (Exactly 1 per NIFL club):**

   $$\sum_{i \in Club_c} x_i = 1 \quad \forall c \in Clubs$$

4. **Positional Requirements:**

   $$\sum_{i \in GK} x_i = 1, \quad \sum_{i \in AM} x_i = 1$$

## 📂 Project Structure

```text
NIFL_optimizer/
├── data/
│   ├── historical_points.csv
│   ├── master_sunday_life.csv
│   ├── nifl_squad_numbers_26_27_clean.csv
│   └── player_projections.csv
├── .gitignore
├── README.md
├── app.py
├── generate_projections.py
├── optimizer.py
└── requirements.txt
🛠️ Installation and Setup
Clone the repository:

Bash
git clone [https://github.com/yourusername/NIFL_optimizer.git](https://github.com/yourusername/NIFL_optimizer.git)
cd NIFL_optimizer
Create a virtual environment and install dependencies:

Bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
Generate the projections:

Bash
python generate_projections.py
Launch the Optimizer Dashboard:

Bash
streamlit run app.py

