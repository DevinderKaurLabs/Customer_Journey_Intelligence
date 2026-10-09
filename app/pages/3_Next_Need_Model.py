"""Next-Need Model: does it actually predict better than 'show what's popular'?"""
import plotly.graph_objects as go
import streamlit as st

from common import NAVY, SKY, TEAL, kpi, load_outputs, setup, source_badge

setup("Next-Need Model")
d = load_outputs()
ev = d["evaluation"]

st.title("Next-Need Model")
st.markdown(
    "**The test.** Freeze everything we knew on the cutoff date. Predict each customer's top 5 next needs. "
    "Then look at what they actually explored in the next 30 days — a need they had **never touched before**. "
    "A hit means at least one of those new needs was in our top 5."
)
source_badge(d["meta"])

models = {"popularity": ("Show what's popular", SKY), "transitions": ("Predict the next need", NAVY),
          "transitions+mission": ("…+ boost inside the mission", TEAL)}
segs = ["all customers", "in a mission", "no mission"]
fig = go.Figure()
for m, (label, color) in models.items():
    sub = ev[ev["model"] == m].set_index("segment").reindex(segs)
    fig.add_bar(name=label, x=[s.title() for s in segs], y=sub["hit_rate"], marker_color=color,
                text=[f"{v:.0%}" for v in sub["hit_rate"]], textposition="outside",
                hovertemplate="%{x}: %{y:.1%} hit rate<extra>" + label + "</extra>")
fig.update_layout(barmode="group", height=420, yaxis=dict(visible=False, range=[0, 1.05]),
                  margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                  legend=dict(orientation="h", y=1.12))
st.plotly_chart(fig, width="stretch")

e = ev.set_index(["segment", "model"])
c1, c2, c3 = st.columns(3)
kpi(c1, f"{e.loc[('all customers', 'transitions'), 'lift_vs_popularity']:.1f}x", "lift vs popularity, all customers")
kpi(c2, f"{e.loc[('all customers', 'transitions'), 'purchase_hit_rate']:.0%}",
    f"of customers who bought a new need had it in our top 5 (popularity: {e.loc[('all customers', 'popularity'), 'purchase_hit_rate']:.0%})")
kpi(c3, f"{int(e.loc[('all customers', 'transitions'), 'users']):,}", "customers in the backtest")

st.subheader("What we learned")
boost_gain = e.loc[("in a mission", "transitions+mission"), "hit_rate"] - e.loc[("in a mission", "transitions"), "hit_rate"]
st.markdown(f"""
- **Sequence beats popularity**, and the gap is biggest for customers inside a life mission — that's where behaviour is most predictable.
- **Boosting candidates inside the detected mission changed the hit rate by {boost_gain:+.1%}.** The transitions already carry the mission
  structure, so the mission's real value is in choosing *what job to do* (stage), not in re-ranking products. We keep the boost off by default in
  evaluation claims and report it honestly.
- **No-mission customers** still benefit, but less. For them, product-level retargeting with fatigue rules is the right default.
""")

with st.expander("Full results table"):
    st.dataframe(ev.round(3), hide_index=True, width="stretch")
with st.expander("What would change our mind"):
    st.markdown("""
- If on real data the next-need model beats popularity by less than ~1.2x, sequence isn't adding much — use simpler category affinity.
- If 'in a mission' customers are *not* more predictable than others, the mission rules are wrong for this catalog — re-tune `config.MISSIONS`.
- Prediction ≠ persuasion. The model finds who will look at what next; only a holdout test shows whether *messaging* them changes what they buy.
  See `docs/experiment_design.md`.
""")
