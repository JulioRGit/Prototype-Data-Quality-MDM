import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Configuration de la page
st.set_page_config(
    page_title="Qualité Master Data Produit",
    page_icon="📊",
    layout="wide"
)

st.title("Qualité & Complétude du Master Data Produit")
st.markdown("Analyse de la complétude et de la fiabilité/cohérence des attributs produit.")

# --- Chargement des données ---
uploaded_file = st.sidebar.file_uploader("Importer le fichier Excel ou CSV", type=["xlsx", "xls", "csv"])

@st.cache_data
def load_data(file):
    if file.name.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file)
    return pd.read_csv(file)

if uploaded_file is not None:
    df = load_data(uploaded_file)
else:
    try:
        df = pd.read_excel("Exemple.xlsx")
        st.info("Données chargées par défaut depuis `Exemple.xlsx`.")
    except Exception:
        st.warning("Veuillez importer un fichier Excel ou CSV pour lancer l'analyse.")
        st.stop()

# --- Fonctions d'analyse de consistance et complétude ---
SUSPECT_STRINGS = {"", "nan", "null", "none", "n/a", "na", "?", "-", "/", "undefined"}

def compute_attribute_metrics(series: pd.Series):
    total = len(series)
    if total == 0:
        return 0.0, 0.0
    
    # 1. Complétude
    is_null = series.isna()
    # Détection de chaînes vides ou de faux-positifs textuels
    if series.dtype == 'object':
        cleaned_str = series.astype(str).str.strip().str.lower()
        is_suspect_null = cleaned_str.isin(SUSPECT_STRINGS)
        missing_mask = is_null | is_suspect_null
    else:
        missing_mask = is_null
        
    valid_count = (~missing_mask).sum()
    completeness = valid_count / total

    if valid_count == 0:
        return 0.0, 0.0

    valid_values = series[~missing_mask]

    # 2. Consistance & Cohérence vis-à-vis de l'ensemble de la distribution
    # Variable numérique
    if pd.api.types.is_numeric_dtype(valid_values):
        numeric_vals = pd.to_numeric(valid_values, errors='coerce').dropna()
        if len(numeric_vals) >= 4:
            q1 = numeric_vals.quantile(0.25)
            q3 = numeric_vals.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 2.5 * iqr
            upper_bound = q3 + 2.5 * iqr
            # Hors bornes = incohérent
            incoherent_mask = (numeric_vals < lower_bound) | (numeric_vals > upper_bound)
            incoherent_ratio = incoherent_mask.mean()
        else:
            incoherent_ratio = 0.0
        consistency = max(0.0, 1.0 - incoherent_ratio)
        
    # Variable catégorielle / texte
    else:
        counts = valid_values.value_counts(normalize=True)
        # Valeurs isolées / anomalies typologiques (< 1% de l'ensemble si échantillon représentatif)
        threshold = 0.01 if len(valid_values) >= 100 else 0.05
        rare_categories = counts[counts < threshold].index
        incoherent_count = valid_values.isin(rare_categories).sum()
        consistency = max(0.0, 1.0 - (incoherent_count / len(valid_values)))

    return completeness, consistency

# Calcul des métriques sur toutes les colonnes
results = []
for col in df.columns:
    comp, cons = compute_attribute_metrics(df[col])
    # Score combiné : 40% complétude + 60% cohérence des données renseignées
    score = (0.4 * comp) + (0.6 * cons)
    
    # Classification à 3 couleurs
    if score >= 0.80 and cons >= 0.75:
        category = "Fiable (Vert)"
        color_code = "#2ECC71"
    elif score >= 0.50:
        category = "Moyennement fiable (Orange)"
        color_code = "#F39C12"
    else:
        category = "Peu fiable / Suspect (Rouge)"
        color_code = "#E74C3C"

    results.append({
        "Attribut": col,
        "Completude": comp * 100,
        "Consistance": cons * 100,
        "Score_Qualite": score * 100,
        "Qualite_Label": category,
        "Couleur": color_code
    })

res_df = pd.DataFrame(results).sort_values("Completude", ascending=True)

# --- 3 KPI en haut ---
nb_produits = len(df)
global_quality = (res_df["Score_Qualite"].mean()) if not res_df.empty else 0
nb_critiques = (res_df["Qualite_Label"] == "Peu fiable / Suspect (Rouge)").sum()

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Nombre de produits", f"{nb_produits:,}".replace(",", " "))
kpi2.metric("Qualité globale pondérée", f"{global_quality:.1f} %")
kpi3.metric("Attributs critiques (Rouge)", nb_critiques)

st.markdown("---")

# --- Graphique de complétude et consistance ---
st.subheader("Complétude et fiabilité par attribut")

color_map = {
    "Fiable (Vert)": "#2ECC71",
    "Moyennement fiable (Orange)": "#F39C12",
    "Peu fiable / Suspect (Rouge)": "#E74C3C"
}

fig = px.bar(
    res_df,
    x="Completude",
    y="Attribut",
    orientation="h",
    color="Qualite_Label",
    color_discrete_map=color_map,
    hover_data={
        "Completude": ":.1f%",
        "Consistance": ":.1f%",
        "Score_Qualite": ":.1f%",
        "Qualite_Label": False
    },
    labels={
        "Completude": "% de complétude",
        "Attribut": "Attribut produit",
        "Qualite_Label": "Niveau de fiabilité"
    },
    height=max(500, len(res_df) * 26)
)

fig.update_layout(
    xaxis=dict(range=[0, 105], ticksuffix="%"),
    yaxis=dict(autorange="reversed"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=10, r=20, t=40, b=30)
)

st.plotly_chart(fig, use_container_width=True)

# Tableau détaillé
with st.expander("Consulter le détail chiffré par attribut"):
    st.dataframe(
        res_df[["Attribut", "Completude", "Consistance", "Score_Qualite", "Qualite_Label"]]
        .sort_values("Score_Qualite", ascending=False)
        .style.format({
            "Completude": "{:.1f} %",
            "Consistance": "{:.1f} %",
            "Score_Qualite": "{:.1f} %"
        }),
        use_container_width=True
    )