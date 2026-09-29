"""MovieLens Dashboard — Streamlit + Plotly."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DATA_PATH = Path(__file__).parent / "data" / "movie_ratings.csv"

CHART_COLOR = "#2563eb"
CHART_COLOR_2 = "#0f766e"
MUTED = "#64748b"

px.defaults.template = "plotly_white"


@st.cache_data(show_spinner=False)
def load_ratings() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["rating", "movie_id", "title"])
    return df


@st.cache_data(show_spinner=False)
def explode_genres(ratings: pd.DataFrame) -> pd.DataFrame:
    exploded = ratings.copy()
    exploded["genre"] = exploded["genres"].fillna("unknown").str.split("|")
    exploded = exploded.explode("genre")
    exploded["genre"] = exploded["genre"].str.strip()
    exploded = exploded[exploded["genre"].ne("") & exploded["genre"].notna()]
    return exploded


def apply_filters(
    ratings: pd.DataFrame,
    year_min: int,
    year_max: int,
    selected_genres: list[str],
) -> pd.DataFrame:
    has_year = ratings["year"].notna()
    in_range = ratings["year"].between(year_min, year_max)
    filtered = ratings.loc[~has_year | in_range]
    if selected_genres:
        tagged = explode_genres(filtered)
        keep_ids = tagged.loc[tagged["genre"].isin(selected_genres), "movie_id"].unique()
        filtered = filtered.loc[filtered["movie_id"].isin(keep_ids)]
    return filtered


def sorted_bar(
    frame: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    x_title: str,
    y_title: str,
    color: str = CHART_COLOR,
    hover_data: dict | None = None,
    text: str | None = None,
) -> go.Figure:
    fig = px.bar(
        frame,
        x=x,
        y=y,
        orientation="h",
        title=title,
        hover_data=hover_data,
        text=text,
    )
    fig.update_traces(marker_color=color, textposition="outside")
    fig.update_layout(
        yaxis={"categoryorder": "array", "categoryarray": frame[y].tolist()},
        xaxis_title=x_title,
        yaxis_title=y_title,
        margin=dict(l=20, r=40, t=60, b=40),
        height=max(380, 28 * len(frame) + 120),
    )
    return fig


def main() -> None:
    st.set_page_config(
        page_title="MovieLens Dashboard",
        page_icon=":clapper:",
        layout="wide",
    )
    ratings = load_ratings()
    genre_rows = explode_genres(ratings)
    all_genres = sorted(
        g for g in genre_rows["genre"].unique() if str(g).lower() != "unknown"
    )

    year_valid = ratings["year"].dropna()
    data_year_min = int(year_valid.min())
    data_year_max = int(year_valid.max())

    st.title("MovieLens Dashboard")
    st.caption(
        "100,000 ratings from 943 users on 1,682 movies (MovieLens 100K). "
        "Use the sidebar to filter release year and genres."
    )

    with st.sidebar:
        st.header("Filters")
        year_min, year_max = st.slider(
            "Movie release year",
            min_value=data_year_min,
            max_value=data_year_max,
            value=(data_year_min, data_year_max),
        )
        selected_genres = st.multiselect(
            "Genres (movies matching any selected)",
            options=all_genres,
            default=[],
            help="Leave empty to include every genre. Multi-genre movies count if they match any selection.",
        )
        st.divider()
        st.header("Best-movies floor")
        rating_floor = st.slider(
            "Minimum number of ratings",
            min_value=10,
            max_value=300,
            value=50,
            step=10,
            help="Only movies with at least this many ratings (in the current filters) can appear in the ranking.",
        )
        compare_floors = st.checkbox("Compare floor 50 vs 150", value=True)

    filtered = apply_filters(ratings, year_min, year_max, selected_genres)
    filtered_genres = explode_genres(filtered)

    n_ratings = len(filtered)
    n_movies = filtered["movie_id"].nunique()
    n_users = filtered["user_id"].nunique()
    mean_rating = filtered["rating"].mean() if n_ratings else float("nan")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ratings", f"{n_ratings:,}")
    c2.metric("Movies", f"{n_movies:,}")
    c3.metric("Users", f"{n_users:,}")
    c4.metric("Mean rating", f"{mean_rating:.2f}" if n_ratings else "—")

    if n_ratings == 0:
        st.warning("No ratings match the current filters. Widen the year range or genre selection.")
        return

    # --- Genre breakdown: unique rated movies per genre ---
    genre_for_charts = filtered_genres[filtered_genres["genre"].str.lower() != "unknown"]
    movie_genre = (
        genre_for_charts.drop_duplicates(["movie_id", "genre"])
        .groupby("genre", as_index=False)
        .agg(n_movies=("movie_id", "nunique"), n_ratings=("rating", "size"))
        .sort_values("n_movies", ascending=True)
    )

    # --- Genre satisfaction ---
    genre_sat = (
        genre_for_charts.groupby("genre", as_index=False)
        .agg(
            mean_rating=("rating", "mean"),
            n_ratings=("rating", "size"),
            n_movies=("movie_id", "nunique"),
        )
        .sort_values("mean_rating", ascending=True)
    )
    genre_sat["mean_rating"] = genre_sat["mean_rating"].round(3)
    highest = genre_sat.iloc[-1]
    lowest = genre_sat.iloc[0]

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Genre breakdown",
            "Genre satisfaction",
            "Ratings over time",
            "Best movies (floor)",
        ]
    )

    with tab1:
        st.subheader("Distribution of genres among rated movies")
        st.write(
            "Each movie is counted once per genre tag. A film tagged "
            "`Drama|Romance` contributes to both Drama and Romance."
        )
        fig = sorted_bar(
            movie_genre,
            x="n_movies",
            y="genre",
            title="Unique rated movies by genre",
            x_title="Number of movies",
            y_title="Genre",
            hover_data={"n_ratings": True},
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Source: MovieLens 100K ratings extract · unique movie–genre pairs after filters.")

    with tab2:
        st.subheader("Which genres rate highest and lowest?")
        h1, h2 = st.columns(2)
        h1.metric(
            "Highest average",
            f"{highest['genre']}",
            f"{highest['mean_rating']:.3f} ({int(highest['n_ratings']):,} ratings)",
        )
        h2.metric(
            "Lowest average",
            f"{lowest['genre']}",
            f"{lowest['mean_rating']:.3f} ({int(lowest['n_ratings']):,} ratings)",
            delta_color="inverse",
        )
        fig = sorted_bar(
            genre_sat,
            x="mean_rating",
            y="genre",
            title="Average rating by genre",
            x_title="Mean rating (1–5)",
            y_title="Genre",
            color=CHART_COLOR_2,
            hover_data={"n_ratings": True, "n_movies": True},
        )
        fig.update_xaxes(range=[min(1, genre_sat["mean_rating"].min() - 0.15), 5])
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Source: MovieLens 100K · mean of individual ratings after exploding multi-genre tags."
        )

    with tab3:
        st.subheader("Mean rating by movie release year")
        by_year = (
            filtered.dropna(subset=["year"])
            .assign(release_year=lambda d: d["year"].astype(int))
            .groupby("release_year", as_index=False)
            .agg(
                mean_rating=("rating", "mean"),
                n_ratings=("rating", "size"),
                n_movies=("movie_id", "nunique"),
            )
            .sort_values("release_year")
        )
        min_n = st.slider(
            "Hide years with fewer than this many ratings",
            min_value=1,
            max_value=int(max(50, by_year["n_ratings"].median())),
            value=20,
            help="Early decades have sparse titles; raising this reduces noisy year means.",
        )
        by_year_plot = by_year[by_year["n_ratings"] >= min_n]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=by_year_plot["release_year"],
                y=by_year_plot["mean_rating"],
                mode="lines+markers",
                name="Mean rating",
                line=dict(color=CHART_COLOR, width=2),
                marker=dict(size=6),
                customdata=by_year_plot[["n_ratings", "n_movies"]],
                hovertemplate=(
                    "Release year %{x}<br>Mean rating %{y:.3f}"
                    "<br>Ratings %{customdata[0]:,}<br>Movies %{customdata[1]:,}<extra></extra>"
                ),
            )
        )
        fig.update_layout(
            title="Mean rating across movie release years",
            xaxis_title="Release year",
            yaxis_title="Mean rating (1–5)",
            margin=dict(l=20, r=20, t=60, b=40),
            height=420,
        )
        fig.update_yaxes(range=[2.5, 5])
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Source: MovieLens 100K · mean of ratings grouped by the movie's release year (not the rating date)."
        )

    with tab4:
        st.subheader("Top 5 movies after a ratings-count floor")
        st.write(
            "Averages on tiny samples can look perfect. This ranking only keeps movies "
            f"with **at least {rating_floor} ratings** in the current filter set."
        )

        def top_n(frame: pd.DataFrame, floor: int, n: int = 5) -> pd.DataFrame:
            stats = (
                frame.groupby(["movie_id", "title"], as_index=False)
                .agg(mean_rating=("rating", "mean"), n_ratings=("rating", "size"))
            )
            stats = stats[stats["n_ratings"] >= floor].copy()
            stats = stats.sort_values(
                ["mean_rating", "n_ratings"], ascending=[False, False]
            ).head(n)
            stats["mean_rating"] = stats["mean_rating"].round(3)
            stats["label"] = stats.apply(
                lambda r: f"{r['title']} ({int(r['n_ratings'])})", axis=1
            )
            return stats.sort_values("mean_rating", ascending=True)

        top_current = top_n(filtered, rating_floor)
        if top_current.empty:
            st.warning(
                f"No movies have {rating_floor}+ ratings under the current filters."
            )
        else:
            fig = sorted_bar(
                top_current,
                x="mean_rating",
                y="label",
                title=f"Top 5 movies with at least {rating_floor} ratings",
                x_title="Mean rating (1–5)",
                y_title="Movie (rating count)",
                hover_data={"n_ratings": True, "title": True},
            )
            fig.update_xaxes(range=[3.5, 5])
            st.plotly_chart(fig, use_container_width=True)

        if compare_floors:
            st.markdown("#### What changes from a floor of 50 to 150?")
            top_50 = top_n(filtered, 50)
            top_150 = top_n(filtered, 150)
            left, right = st.columns(2)
            with left:
                st.caption("Floor = 50")
                if top_50.empty:
                    st.info("No movies meet a floor of 50 with current filters.")
                else:
                    fig50 = sorted_bar(
                        top_50,
                        x="mean_rating",
                        y="label",
                        title="Top 5 · min 50 ratings",
                        x_title="Mean rating",
                        y_title="",
                        color=CHART_COLOR,
                    )
                    fig50.update_xaxes(range=[3.5, 5])
                    fig50.update_layout(height=320, margin=dict(t=50, l=10, r=10, b=30))
                    st.plotly_chart(fig50, use_container_width=True)
            with right:
                st.caption("Floor = 150")
                if top_150.empty:
                    st.info("No movies meet a floor of 150 with current filters.")
                else:
                    fig150 = sorted_bar(
                        top_150,
                        x="mean_rating",
                        y="label",
                        title="Top 5 · min 150 ratings",
                        x_title="Mean rating",
                        y_title="",
                        color=CHART_COLOR_2,
                    )
                    fig150.update_xaxes(range=[3.5, 5])
                    fig150.update_layout(height=320, margin=dict(t=50, l=10, r=10, b=30))
                    st.plotly_chart(fig150, use_container_width=True)

            if not top_50.empty and not top_150.empty:
                titles_50 = set(top_50["title"])
                titles_150 = set(top_150["title"])
                dropped = sorted(titles_50 - titles_150)
                added = sorted(titles_150 - titles_50)
                kept = sorted(titles_50 & titles_150)
                st.write(
                    f"**Stay in the top 5:** {', '.join(kept) if kept else 'none'}. "
                    f"**Drop when the floor rises to 150:** {', '.join(dropped) if dropped else 'none'}. "
                    f"**Enter at 150:** {', '.join(added) if added else 'none'}."
                )
                st.caption(
                    "Raising the floor typically removes well-loved but less-rated titles "
                    "(for example Wallace & Gromit shorts) in favor of widely rated classics."
                )

        st.caption("Source: MovieLens 100K · movie-level mean rating after applying the count floor.")


if __name__ == "__main__":
    main()
