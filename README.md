
# MovieLens Dashboard

Interactive Streamlit dashboard for the MovieLens 100K ratings extract (`data/movie_ratings.csv`).

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Charts

- **Genre breakdown** — unique rated movies per genre
- **Genre satisfaction** — average rating by genre
- **Ratings over time** — mean rating by movie release year
- **Best movies with a floor** — top 5 titles at a minimum-rating threshold, with a 50 vs 150 comparison
