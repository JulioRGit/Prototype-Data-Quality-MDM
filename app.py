import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------
# Page Configuration & Theme-Adaptive Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="PROTOTYPE Product Data Master Quality Cockpit",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* Metric container adaptive to both Light and Dark mode */
    [data-testid="stMetric"] {
        background-color: var(--secondary-background-color) !important;
        padding: 16px 20px !important;
        border-radius: 10px !important;
        border: 1px solid rgba(128, 128, 128, 0.2) !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08) !important;
    }

    /* Force metric label color based on theme */
    [data-testid="stMetricLabel"] {
        color: var(--text-color) !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
    }

    /* Force metric value text visibility */
    [data-testid="stMetricValue"] {
        color: var(--text-color) !important;
        font-weight: 700 !important;
    }

    /* Legible delta badges */
    [data-testid="stMetricDelta"] {
        font-size: 0.85rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Data Families Definition (~5 attributes per family)
# ---------------------------------------------------------
DATA_FAMILIES = {
    "Core Identification & Hierarchy": {
        "attributes": [
            "NAME",
            "CONTENT_PH_CODE",
            "ARTICLE_PH_CODE_7",
            "MODEL_COMMERCIAL_NAME",
            "MODEL_SLAB",
        ],
        "business_value": 9.2,  # 0 (Low) to 10 (Critical)
        "ease_of_fix": 7.8,     # 0 (Very Complex) to 10 (Very Easy)
        "description": "Essential product keys and commercial names required across all downstream systems.",
    },
    "Commercial Hierarchy & Franchise": {
        "attributes": [
            "MODEL_FRANCHISE",
            "MODEL_SUB_FRANCHISE",
            "MODEL_PRD_TYPE_CODE",
            "PP_PRODUCT_TYPE",
            "PRODUCT_USAGE",
        ],
        "business_value": 8.0,
        "ease_of_fix": 6.5,
        "description": "Commercial grouping, franchise lineage, and product usage codes.",
    },
    "Sizing, Fit & Demographics": {
        "attributes": [
            "SKU_SIZE_CODE",
            "FIT_CLASSIFICATION",
            "FIT_CLASSIFICATION.1",
            "MODEL_GENDER",
            "SKU_NET_WEIGHT",
        ],
        "business_value": 8.8,
        "ease_of_fix": 8.2,
        "description": "Customer-facing fit, sizes, and physical shipping weight specifications.",
    },
    "Technical Materials & Sustainability": {
        "attributes": [
            "MODEL_MEMBRANE",
            "MODEL_INLAYSOLE_MCL",
            "MODEL_LINING_MCL",
            "MODEL_OUTSOLE_MCL",
            "MODEL_RECYCLABILITY",
        ],
        "business_value": 6.8,
        "ease_of_fix": 3.8,
        "description": "Technical lab components and sustainability claims needing supplier input.",
    },
    "Customs, Composition & Colors": {
        "attributes": [
            "CUSTOMS_TARGET",
            "MODEL_FEDAS_CODE",
            "EU_LEATHER",
            "EU_SYNTH",
            "EU_TEXTILE",
            "ARTICLE_COLOR_2",
            "ARTICLE_COLOR_3",
        ],
        "business_value": 9.5,
        "ease_of_fix": 5.0,
        "description": "HS/Customs classifications, FEDAS codes, and statutory upper composition sums.",
    },
}

SUSPECT_STRINGS = {
    "-",
    "?",
    "n/a",
    "na",
    "none",
    "null",
    "tbd",
    "undefined",
    "unknown",
    ".",
    "0",
    "empty",
}

# ---------------------------------------------------------
# Quality & Consistency Audit Engine
# ---------------------------------------------------------
def run_data_audit(df: pd.DataFrame):
    total_rows = len(df)
    issues_list = []
    col_stats = {
        col: {
            "total": total_rows,
            "populated_count": 0,
            "suspect_count": 0,
            "incoherent_count": 0,
        }
        for col in df.columns
    }

    for idx, row in df.iterrows():
        product_identifier = str(
            row.get("NAME") or row.get("ARTICLE_PH_CODE_7") or f"SKU_Row_{idx + 1}"
        )

        # 1. Generic placeholder & suspect string detection
        for col in df.columns:
            val = row[col]
            if pd.notna(val):
                col_stats[col]["populated_count"] += 1
                val_clean = str(val).strip().lower()
                if val_clean in SUSPECT_STRINGS:
                    col_stats[col]["suspect_count"] += 1
                    issues_list.append(
                        {
                            "Row_ID": idx + 1,
                            "Product_Identifier": product_identifier,
                            "Attribute": col,
                            "Problematic_Value": str(val),
                            "Issue_Category": "Suspect Placeholder",
                            "Reason": f"Contains dummy/placeholder string '{val}' instead of valid master data.",
                        }
                    )

        # 2. Composition Inconsistency (EU_LEATHER + EU_SYNTH + EU_TEXTILE = 100%)
        comp_cols = ["EU_LEATHER", "EU_SYNTH", "EU_TEXTILE"]
        present_comp = [c for c in comp_cols if c in df.columns and pd.notna(row[c])]
        if len(present_comp) > 0:
            sum_comp = sum(float(row[c]) for c in present_comp if isinstance(row[c], (int, float)))
            if abs(sum_comp - 100.0) > 0.5:
                for c in present_comp:
                    col_stats[c]["incoherent_count"] += 1
                issues_list.append(
                    {
                        "Row_ID": idx + 1,
                        "Product_Identifier": product_identifier,
                        "Attribute": "EU_COMPOSITION",
                        "Problematic_Value": f"L:{row.get('EU_LEATHER', 0)}% | S:{row.get('EU_SYNTH', 0)}% | T:{row.get('EU_TEXTILE', 0)}% (Sum={sum_comp:.1f}%)",
                        "Issue_Category": "Logical Incoherence",
                        "Reason": f"Upper composition percentages must equal 100%. Current total is {sum_comp:.1f}%.",
                    }
                )

        # 3. Hierarchy Prefix Check (ARTICLE_PH_CODE_7 vs CONTENT_PH_CODE)
        if "CONTENT_PH_CODE" in df.columns and "ARTICLE_PH_CODE_7" in df.columns:
            p_code = str(row.get("CONTENT_PH_CODE", "")).strip()
            a_code = str(row.get("ARTICLE_PH_CODE_7", "")).strip()
            if p_code and a_code and p_code not in ["nan", "None"] and a_code not in ["nan", "None"]:
                if not a_code.startswith(p_code):
                    col_stats["ARTICLE_PH_CODE_7"]["incoherent_count"] += 1
                    issues_list.append(
                        {
                            "Row_ID": idx + 1,
                            "Product_Identifier": product_identifier,
                            "Attribute": "ARTICLE_PH_CODE_7",
                            "Problematic_Value": a_code,
                            "Issue_Category": "Hierarchy Incoherence",
                            "Reason": f"Article code '{a_code}' does not match Content parent prefix '{p_code}'.",
                        }
                    )

        # 4. Duplicate Attribute Divergence (FIT_CLASSIFICATION vs FIT_CLASSIFICATION.1)
        if "FIT_CLASSIFICATION" in df.columns and "FIT_CLASSIFICATION.1" in df.columns:
            fit1 = str(row.get("FIT_CLASSIFICATION", "")).strip()
            fit2 = str(row.get("FIT_CLASSIFICATION.1", "")).strip()
            if fit1 and fit2 and fit1 not in ["nan", "None"] and fit2 not in ["nan", "None"]:
                if fit1 != fit2:
                    col_stats["FIT_CLASSIFICATION"]["incoherent_count"] += 1
                    col_stats["FIT_CLASSIFICATION.1"]["incoherent_count"] += 1
                    issues_list.append(
                        {
                            "Row_ID": idx + 1,
                            "Product_Identifier": product_identifier,
                            "Attribute": "FIT_CLASSIFICATION.1",
                            "Problematic_Value": f"Col1: '{fit1}' vs Col2: '{fit2}'",
                            "Issue_Category": "Redundant Conflict",
                            "Reason": "Divergent values between primary and mirrored fit classification columns.",
                        }
                    )

        # 5. Weight Bounds & Anomaly Check (SKU_NET_WEIGHT)
        if "SKU_NET_WEIGHT" in df.columns and pd.notna(row["SKU_NET_WEIGHT"]):
            try:
                wt = float(row["SKU_NET_WEIGHT"])
                if wt <= 0.0 or wt > 25.0:
                    col_stats["SKU_NET_WEIGHT"]["incoherent_count"] += 1
                    issues_list.append(
                        {
                            "Row_ID": idx + 1,
                            "Product_Identifier": product_identifier,
                            "Attribute": "SKU_NET_WEIGHT",
                            "Problematic_Value": str(wt),
                            "Issue_Category": "Out of Range",
                            "Reason": f"Physical SKU net weight ({wt} kg) is unrealistic or <= 0.",
                        }
                    )
            except ValueError:
                col_stats["SKU_NET_WEIGHT"]["incoherent_count"] += 1
                issues_list.append(
                    {
                        "Row_ID": idx + 1,
                        "Product_Identifier": product_identifier,
                        "Attribute": "SKU_NET_WEIGHT",
                        "Problematic_Value": str(row["SKU_NET_WEIGHT"]),
                        "Issue_Category": "Type Error",
                        "Reason": "Weight field contains non-numeric characters.",
                    }
                )

        # 6. Gender Domain Constraints (MODEL_GENDER)
        if "MODEL_GENDER" in df.columns and pd.notna(row["MODEL_GENDER"]):
            valid_genders = {"M", "W", "U", "K", "MEN", "WOMEN", "UNISEX", "KIDS"}
            g_val = str(row["MODEL_GENDER"]).strip().upper()
            if g_val not in valid_genders:
                col_stats["MODEL_GENDER"]["incoherent_count"] += 1
                issues_list.append(
                    {
                        "Row_ID": idx + 1,
                        "Product_Identifier": product_identifier,
                        "Attribute": "MODEL_GENDER",
                        "Problematic_Value": str(row["MODEL_GENDER"]),
                        "Issue_Category": "Invalid Domain Value",
                        "Reason": f"Gender code '{row['MODEL_GENDER']}' is not in approved reference list (M, W, U, K).",
                    }
                )

    attr_summary = []
    for col, st_dict in col_stats.items():
        pop_count = st_dict["populated_count"]
        comp_pct = round((pop_count / total_rows) * 100, 1) if total_rows > 0 else 0.0

        # Incoherent defects carry higher penalty than mild suspect values
        total_defects = (st_dict["suspect_count"] * 1.0) + (st_dict["incoherent_count"] * 2.0)
        if pop_count > 0:
            consist_pct = max(0.0, round((1.0 - (total_defects / pop_count)) * 100, 1))
        else:
            consist_pct = 0.0

        attr_summary.append(
            {
                "Attribute": col,
                "Completeness_Pct": comp_pct,
                "Consistency_Pct": consist_pct,
                "Populated_Count": pop_count,
                "Suspect_Count": st_dict["suspect_count"],
                "Incoherent_Count": st_dict["incoherent_count"],
            }
        )

    summary_df = pd.DataFrame(attr_summary)
    issues_df = pd.DataFrame(issues_list)
    return summary_df, issues_df


# ---------------------------------------------------------
# Sidebar Controls & File Loading
# ---------------------------------------------------------
st.sidebar.title("🛠️ Master Data Controls")
uploaded_file = st.sidebar.file_uploader(
    "Upload Master Data File (.xlsx, .csv)", type=["xlsx", "xls", "csv"]
)

@st.cache_data
def load_data(file_source):
    if file_source is not None:
        if file_source.name.endswith(".csv"):
            return pd.read_csv(file_source)
        return pd.read_excel(file_source)
    try:
        return pd.read_excel("Exemple.xlsx")
    except Exception:
        cols = [
            "SKU_NET_WEIGHT", "SKU_SIZE_CODE", "CONTENT_PH_CODE", "ARTICLE_PH_CODE_7",
            "ARTICLE_COLOR_2", "ARTICLE_COLOR_3", "NAME", "FIT_CLASSIFICATION",
            "MODEL_COMMERCIAL_NAME", "MODEL_PRD_TYPE_CODE", "CUSTOMS_TARGET",
            "MODEL_FEDAS_CODE", "FIT_CLASSIFICATION.1", "MODEL_FRANCHISE", "MODEL_GENDER",
            "MODEL_INLAYSOLE_MCL", "MODEL_LINING_MCL", "MODEL_MEMBRANE", "MODEL_OUTSOLE_MCL",
            "PP_PRODUCT_TYPE", "MODEL_RECYCLABILITY", "MODEL_SLAB", "MODEL_SUB_FRANCHISE",
            "EU_LEATHER", "EU_SYNTH", "EU_TEXTILE", "PRODUCT_USAGE"
        ]
        return pd.DataFrame(columns=cols)

df_raw = load_data(uploaded_file)

if df_raw.empty:
    st.error("No data found. Please upload a valid Product Master Data Excel or CSV file.")
    st.stop()

# ---------------------------------------------------------
# Interactive Weights & View Controls
# ---------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Quality Score Weights")
weight_completeness = st.sidebar.slider(
    "Completeness Weight", min_value=0.0, max_value=1.0, value=0.40, step=0.05
)
weight_consistency = round(1.0 - weight_completeness, 2)
st.sidebar.caption(
    f"Formula: **{weight_completeness*100:.0f}% Completeness** + **{weight_consistency*100:.0f}% Consistency**"
)

chart_metric_mode = st.sidebar.radio(
    "Graph 1 Metric Display:",
    ["Weighted Quality Score (%)", "Raw Completeness Rate (%)"],
)

# Run raw audit
summary_df, issues_df = run_data_audit(df_raw)

# ---------------------------------------------------------
# Dynamic Quality Calculation Engine
# ---------------------------------------------------------
summary_df["Weighted_Quality_Score"] = (
    (summary_df["Completeness_Pct"] * weight_completeness)
    + (summary_df["Consistency_Pct"] * weight_consistency)
).round(1)

# Dynamic 3-color tier allocation based on the weighted quality score
def compute_quality_tier(score):
    if score >= 75.0:
        return "High Reliability"
    elif score >= 50.0:
        return "Moderate Quality"
    else:
        return "Low Reliability (Critical)"

summary_df["Reliability_Tier"] = summary_df["Weighted_Quality_Score"].apply(compute_quality_tier)

sort_field = "Weighted_Quality_Score" if "Weighted" in chart_metric_mode else "Completeness_Pct"
summary_df = summary_df.sort_values(sort_field, ascending=True)

# ---------------------------------------------------------
# Top 3 High-Level KPIs
# ---------------------------------------------------------
st.title("📦 Product Master Data Quality Hub")
st.markdown("Automated completeness, consistency audit & remediation prioritization matrix.")

total_products = len(df_raw)
overall_quality = round(summary_df["Weighted_Quality_Score"].mean(), 1)
red_attributes_count = int((summary_df["Reliability_Tier"] == "Low Reliability (Critical)").sum())

col_kpi1, col_kpi2, col_kpi3 = st.columns(3)

with col_kpi1:
    st.metric(
        label="Total Products Audited",
        value=f"{total_products:,}",
        help="Number of SKU rows analyzed in Master Data",
    )

with col_kpi2:
    st.metric(
        label=f"Overall Quality ({weight_completeness*100:.0f}% Comp / {weight_consistency*100:.0f}% Cons)",
        value=f"{overall_quality:.1f}%",
        delta=f"{red_attributes_count} critical attributes",
        delta_color="normal" if overall_quality >= 75 else "inverse",
        help="Weighted score combining completeness and consistency across all attributes",
    )

with col_kpi3:
    st.metric(
        label="Critical (Red) Attributes",
        value=red_attributes_count,
        delta=f"Weighted score < 50%" if red_attributes_count > 0 else "All Clean",
        delta_color="inverse" if red_attributes_count > 0 else "normal",
        help="Attributes with dynamic weighted quality below 50%",
    )

st.markdown("---")

# ---------------------------------------------------------
# Graph 1: Attribute Quality & Consistency Bar Chart
# ---------------------------------------------------------
st.subheader("1. Attribute Completeness & Quality Tiering")
st.caption(
    f"Currently displaying: **{chart_metric_mode}**. "
    "Bars and colors update dynamically as you change weights in the sidebar: "
    "🟢 **Green**: High Reliability (≥75%) | 🟠 **Orange**: Moderate (50%-74%) | 🔴 **Red**: Critical (<50%)"
)

fig_bar = px.bar(
    summary_df,
    x=sort_field,
    y="Attribute",
    orientation="h",
    color="Reliability_Tier",
    color_discrete_map={
        "High Reliability": "#43A047",
        "Moderate Quality": "#FB8C00",
        "Low Reliability (Critical)": "#E53935",
    },
    category_orders={
        "Reliability_Tier": ["High Reliability", "Moderate Quality", "Low Reliability (Critical)"]
    },
    hover_data={
        "Weighted_Quality_Score": ":.1f%",
        "Completeness_Pct": ":.1f%",
        "Consistency_Pct": ":.1f%",
        "Populated_Count": True,
        "Suspect_Count": True,
        "Incoherent_Count": True,
        "Reliability_Tier": True,
    },
    height=max(550, len(summary_df) * 24),
    labels={
        sort_field: chart_metric_mode,
        "Attribute": "Master Data Attribute",
        "Reliability_Tier": "Reliability Status",
    },
)

fig_bar.update_layout(
    xaxis=dict(range=[0, 105], ticks="outside", dtick=10),
    yaxis=dict(autorange="reversed"),
    margin=dict(l=20, r=20, t=30, b=30),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    template="plotly_white",
)
st.plotly_chart(fig_bar, use_container_width=True)

# ---------------------------------------------------------
# Table: Detailed Unreliable Values & Explanations
# ---------------------------------------------------------
st.subheader("2. Audit Log of Suspect & Incoherent Values")

if not issues_df.empty:
    col_filter1, col_filter2, col_filter3 = st.columns([1, 1, 2])
    with col_filter1:
        selected_attr = st.selectbox(
            "Filter by Attribute:",
            ["All Attributes"] + sorted(issues_df["Attribute"].unique().tolist()),
        )
    with col_filter2:
        selected_category = st.selectbox(
            "Filter by Issue Category:",
            ["All Categories"] + sorted(issues_df["Issue_Category"].unique().tolist()),
        )
    with col_filter3:
        search_kw = st.text_input("Search in Explanations / Products:", "")

    filtered_issues = issues_df.copy()
    if selected_attr != "All Attributes":
        filtered_issues = filtered_issues[filtered_issues["Attribute"] == selected_attr]
    if selected_category != "All Categories":
        filtered_issues = filtered_issues[filtered_issues["Issue_Category"] == selected_category]
    if search_kw:
        filtered_issues = filtered_issues[
            filtered_issues["Reason"].str.contains(search_kw, case=False, na=False)
            | filtered_issues["Product_Identifier"].str.contains(search_kw, case=False, na=False)
        ]

    st.dataframe(
        filtered_issues,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Row_ID": st.column_config.NumberColumn("Row #", width="small"),
            "Product_Identifier": st.column_config.TextColumn("Product / SKU", width="medium"),
            "Attribute": st.column_config.TextColumn("Attribute Name", width="medium"),
            "Problematic_Value": st.column_config.TextColumn("Flagged Value", width="medium"),
            "Issue_Category": st.column_config.TextColumn("Issue Category", width="small"),
            "Reason": st.column_config.TextColumn("Diagnostic & Reason for Inconsistency", width="large"),
        },
    )

    csv_data = filtered_issues.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Export Filtered Audit Log to CSV",
        data=csv_data,
        file_name="master_data_quality_issues.csv",
        mime="text/csv",
    )
else:
    st.success("🎉 No suspicious or incoherent values detected across audited attributes!")

st.markdown("---")

# ---------------------------------------------------------
# Graph 2: Action Matrix (Business Value vs Ease of Improvement)
# ---------------------------------------------------------
st.subheader("3. Governance Prioritization Matrix: Data Families")
st.caption(
    "Attributes are grouped into 5 Data Families (~5 attributes each). "
    "Bubble size and color reflect the **dynamically weighted quality score**."
)

family_records = []
for f_name, f_data in DATA_FAMILIES.items():
    matched_cols = [c for c in f_data["attributes"] if c in df_raw.columns]
    f_summary = summary_df[summary_df["Attribute"].isin(matched_cols)]

    avg_comp = f_summary["Completeness_Pct"].mean() if not f_summary.empty else 0.0
    avg_cons = f_summary["Consistency_Pct"].mean() if not f_summary.empty else 0.0
    family_quality = round((avg_comp * weight_completeness) + (avg_cons * weight_consistency), 1)

    family_records.append(
        {
            "Data_Family": f_name,
            "Business_Value": f_data["business_value"],
            "Ease_of_Improvement": f_data["ease_of_fix"],
            "Attributes_Count": len(matched_cols),
            "Attributes_List": ", ".join(matched_cols),
            "Family_Quality_Score": family_quality,
            "Description": f_data["description"],
        }
    )

family_df = pd.DataFrame(family_records)

fig_matrix = go.Figure()

# Background Quadrant Shading
# Top-Right: Quick Wins
fig_matrix.add_shape(
    type="rect", x0=5, x1=10, y0=5, y1=10,
    fillcolor="rgba(76, 175, 80, 0.12)", line=dict(width=0), layer="below"
)
# Bottom-Right: Major Strategic Projects
fig_matrix.add_shape(
    type="rect", x0=5, x1=10, y0=0, y1=5,
    fillcolor="rgba(33, 150, 243, 0.08)", line=dict(width=0), layer="below"
)
# Top-Left: Low Hanging Fruits
fig_matrix.add_shape(
    type="rect", x0=0, x1=5, y0=5, y1=10,
    fillcolor="rgba(255, 193, 7, 0.08)", line=dict(width=0), layer="below"
)
# Bottom-Left: Deprioritized
fig_matrix.add_shape(
    type="rect", x0=0, x1=5, y0=0, y1=5,
    fillcolor="rgba(158, 158, 158, 0.12)", line=dict(width=0), layer="below"
)

# Reference midlines
fig_matrix.add_vline(x=5, line_width=1.2, line_dash="dash", line_color="#757575")
fig_matrix.add_hline(y=5, line_width=1.2, line_dash="dash", line_color="#757575")

# Quadrant Annotations
fig_matrix.add_annotation(x=8.5, y=9.5, text="⭐ QUICK WINS<br>(High Value, Easy to Fix)", showarrow=False, font=dict(color="#2e7d32", size=12, family="Arial Black"))
fig_matrix.add_annotation(x=8.5, y=0.8, text="🏗️ STRATEGIC PROJECTS<br>(High Value, Complex)", showarrow=False, font=dict(color="#1565c0", size=11))
fig_matrix.add_annotation(x=1.5, y=9.5, text="🌱 SECONDARY GAINS<br>(Low Value, Easy to Fix)", showarrow=False, font=dict(color="#b78103", size=11))
fig_matrix.add_annotation(x=1.5, y=0.8, text="⏳ DEPRIORITIZE<br>(Low Value, Complex)", showarrow=False, font=dict(color="#616161", size=11))

# Bubble scatter trace
fig_matrix.add_trace(
    go.Scatter(
        x=family_df["Business_Value"],
        y=family_df["Ease_of_Improvement"],
        mode="markers+text",
        text=family_df["Data_Family"],
        textposition="top center",
        marker=dict(
            size=[max(26, q * 0.48) for q in family_df["Family_Quality_Score"]],
            color=family_df["Family_Quality_Score"],
            colorscale="RdYlGn",
            cmin=0,
            cmax=100,
            showscale=True,
            colorbar=dict(title="Quality (%)", thickness=15, len=0.8),
            line=dict(width=2, color="#212121"),
        ),
        customdata=np.stack(
            (
                family_df["Attributes_Count"],
                family_df["Family_Quality_Score"],
                family_df["Attributes_List"],
                family_df["Description"],
            ),
            axis=-1,
        ),
        hovertemplate=(
            "<b>%{text}</b><br><br>"
            "• Business Value: <b>%{x:.1f} / 10</b><br>"
            "• Ease of Improvement: <b>%{y:.1f} / 10</b><br>"
            "• Weighted Quality: <b>%{customdata[1]:.1f}%</b><br>"
            "• Attributes Count: <b>%{customdata[0]}</b><br>"
            "• Attributes: %{customdata[2]}<br>"
            "• Strategy: <i>%{customdata[3]}</i><extra></extra>"
        ),
    )
)

fig_matrix.update_layout(
    xaxis=dict(title="Business Value (0 = Low Value → 10 = High Strategic Value)", range=[0, 10.5], dtick=1),
    yaxis=dict(title="Ease of Improvement (0 = Very Complex → 10 = Easy to Remediate)", range=[0, 10.5], dtick=1),
    height=600,
    margin=dict(l=20, r=20, t=30, b=30),
    template="plotly_white",
)

st.plotly_chart(fig_matrix, use_container_width=True)

# Family Breakdown Summary Table
with st.expander("🔍 View Family Data Set Details & Remediation Strategy"):
    st.table(
        family_df[
            [
                "Data_Family",
                "Business_Value",
                "Ease_of_Improvement",
                "Family_Quality_Score",
                "Attributes_Count",
            ]
        ].rename(
            columns={
                "Data_Family": "Data Family",
                "Business_Value": "Business Value (/10)",
                "Ease_of_Improvement": "Ease Score (/10)",
                "Family_Quality_Score": f"Weighted Quality (% at {weight_completeness*100:.0f}/{weight_consistency*100:.0f})",
                "Attributes_Count": "Attributes Count",
            }
        )
    )
