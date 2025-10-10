#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import re, difflib, time, toml, sqlite3, hashlib, os

# ============================
# CONFIGURATION
# ============================
st.set_page_config(page_title="Raw to Ready", page_icon="🧹", layout="wide")

if os.path.exists(".streamlit/config.toml"):
    config = toml.load(".streamlit/config.toml")

# ============================
# DATABASE SETUP
# ============================
DB_PATH = "users.db"
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT
        )
    """)
    conn.commit(); conn.close()

def hash_password(pw): 
    return hashlib.sha256(pw.encode()).hexdigest()

def register_user(username, email, pw):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, email, password_hash) VALUES (?,?,?)",
                  (username, email, hash_password(pw)))
        conn.commit(); return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(email, pw):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=? AND password_hash=?", 
              (email, hash_password(pw)))
    user = c.fetchone()
    conn.close()
    return user

init_db()

# ============================
# SESSION INITIALIZATION
# ============================
for key, val in {"logged_in": False, "username": "", "email": ""}.items():
    if key not in st.session_state:
        st.session_state[key] = val

if "show_register" not in st.session_state:
    st.session_state["show_register"] = False

# ============================
# CUSTOM THEME CSS
# ============================
theme_css = """
<style>
body { background-color: #F4F6F6; }
.main-title {text-align:center;font-size:2.5em;font-weight:bold;color:#2E86C1;}
.subtitle {text-align:center;font-size:1.2em;color:#555;margin-bottom:30px;}
a.auth-link {color:#2E86C1;text-decoration:none;font-weight:600;}
a.auth-link:hover {text-decoration:underline;}
</style>
"""
st.markdown(theme_css, unsafe_allow_html=True)

# ============================
# LOGIN / REGISTER (Unified)
# ============================
def is_valid_email(email: str) -> bool:
    """Validate email format using regex."""
    pattern = r"^[^@]+@[^@]+\.[^@]+$"
    return re.match(pattern, email) is not None

def show_auth_page():
    if not st.session_state["show_register"]:
        st.markdown("## 🔐 Login to Raw2Ready")
        with st.form("login_form"):
            email = st.text_input("Email")
            pw = st.text_input("Password", type="password")

            email = email.strip().lower()

            if st.form_submit_button("Login"):
                user = login_user(email, pw)
                if user:
                    st.session_state.update({
                        "logged_in": True,
                        "username": user[1],
                        "email": user[2]
                    })
                    st.success(f"Welcome back, {user[1]}!")
                    time.sleep(1)
                    st.session_state["show_register"] = False
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please try again.")

        # 👇 Text + Button for Register
        st.markdown("Don’t have an account?")
        if st.button("Register here"):
            st.session_state["show_register"] = True
            st.rerun()

    else:
        st.markdown("## 📝 Create an Account")
        with st.form("register_form"):
            username = st.text_input("Username")
            email = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            cpw = st.text_input("Confirm Password", type="password")

    # Normalize email to lowercase
            email = email.strip().lower()

            if st.form_submit_button("Register"):
                if not all([username, email, pw, cpw]):
                    st.warning("Please fill in all fields.")
                elif not is_valid_email(email):
                    st.error("Please enter a valid email address.")
                elif pw != cpw:
                    st.error("Passwords do not match.")
                elif register_user(username, email, pw):   # <- lowercase email stored
                    st.success("Registration successful! You can now log in.")
                    time.sleep(1)
                    st.session_state["show_register"] = False
                    st.rerun()
                else:
                    st.error("Username or email already exists.")


        # 👇 Text + Button for Login
        st.markdown("Already have an account?")
        if st.button("Back to Login"):
            st.session_state["show_register"] = False
            st.rerun()

# ============================
# PROFILE PAGE
# ============================
def show_profile():
    st.markdown("## My Profile")
    st.write(f"**Username:** {st.session_state['username']}")
    st.write(f"**Email:** {st.session_state['email']}")
    if st.button("Logout"):
        for k in ["logged_in", "username", "email"]:
            st.session_state[k] = "" if k != "logged_in" else False
        st.success("Logged out.")
        time.sleep(1)
        st.rerun()

# ============================
# HELPER FUNCTIONS (DATA CLEANING)
# ============================
def standardize_dates(series):
    def parse_date(x):
        for fmt in ("%Y-%m-%d", "%d/%m/%y", "%d/%m/%Y", "%b %d, %Y", "%Y.%m.%d"):
            try:
                return datetime.strptime(str(x), fmt).strftime("%Y-%m-%d")
            except:
                continue
        return x
    return series.apply(parse_date)

def normalize_text(series, col_name=""):
    """Normalize capitalization for names/cities, but skip emails."""
    if "email" in col_name.lower():
        return series
    return series.astype(str).str.strip().str.lower().str.title()

def validate_emails(series):
    return series.apply(lambda x: x if re.match(r"[^@]+@[^@]+\.[^@]+", str(x)) else "invalid@example.com")

def fill_missing(df, method="Fill with N/A"):
    df_copy = df.copy()
    for col in df_copy.columns:
        if df_copy[col].isnull().sum() > 0:
            if method == "Drop Rows":
                df_copy.dropna(inplace=True)
            elif method == "Fill with N/A":
                df_copy[col].fillna("N/A", inplace=True)
            elif method == "Fill with Mean" and pd.api.types.is_numeric_dtype(df_copy[col]):
                df_copy[col].fillna(df_copy[col].mean(), inplace=True)
            elif method == "Fill with Median" and pd.api.types.is_numeric_dtype(df_copy[col]):
                df_copy[col].fillna(df_copy[col].median(), inplace=True)
            elif method == "Fill by most common":
                df_copy[col].fillna(df_copy[col].mode()[0], inplace=True)
    return df_copy

def fuzzy_standardize(series, cutoff=0.85):
    series = series.astype(str).str.strip()
    unique_vals = series.dropna().unique()
    mapping = {}

    for val in unique_vals:
        match = difflib.get_close_matches(val, mapping.keys(), n=1, cutoff=cutoff)
        if match:
            mapping[val] = mapping[match[0]]
        else:
            mapping[val] = val
    return series.map(mapping)

def detect_anomalies(df, threshold=3):
    anomalies = pd.DataFrame()
    for col in df.select_dtypes(include=[np.number]).columns:
        if df[col].std() == 0:  # avoid divide by zero
            continue
        z_scores = (df[col] - df[col].mean()) / df[col].std()
        anomaly_mask = np.abs(z_scores) > threshold
        if anomaly_mask.any():
            col_anomalies = df[anomaly_mask].copy()
            col_anomalies["Anomaly_Column"] = col
            col_anomalies["Anomaly_Value"] = df[col][anomaly_mask]
            anomalies = pd.concat([anomalies, col_anomalies])
    return anomalies

# ---------------------------
# Reset state when a new file is uploaded
# ---------------------------
def reset_cleaning_options():
    st.session_state["do_duplicates"] = False
    st.session_state["do_standardize_cols"] = False
    st.session_state["do_normalize_text"] = False
    st.session_state["do_fix_dates"] = False
    st.session_state["do_validate_emails"] = False
    st.session_state["do_fuzzy_standardize"] = False
    st.session_state["do_anomaly_detection"] = False
    st.session_state["fill_method"] = "Fill with N/A"
    st.session_state["cleaned_ready"] = False

# ============================
# MAIN APP
# ============================
menu = st.sidebar.radio("Navigation", ["Home","Login / Register","Profile"])

if menu=="Login / Register":
    show_auth_page()

elif menu=="Profile":
    if st.session_state["logged_in"]:
        show_profile()
    else:
        st.warning("Please log in first.")

elif menu=="Home":
    # Hero section
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.image("logo.png", use_container_width=False) 
    st.markdown(
    """
        <p style='font-size:15px; line-height:1.6;'>
        Welcome to <b>Raw to Ready!</b> This tool makes data cleaning super simple — 
        no need to worry about messy spreadsheets. Just upload your CSV, choose what you’d like to fix, 
        and we’ll take care of the rest. In a few clicks, you’ll have a clean, ready-to-use dataset for your projects!
        </p>
        """,unsafe_allow_html=True
    )

    tab1, tab2, tab3 = st.tabs(["Raw Data Preview", "Cleaned Data Preview", "Anomalies Detected"])
    # ---------------------------
    # Sidebar
    # ---------------------------
    st.sidebar.image("logonobg.png", use_container_width=True)
    st.sidebar.markdown("An interactive platform that helps you quickly prepare your dataset for analysis.")
    st.sidebar.markdown("Follow the steps below:")

    # Step 1: Upload
    st.sidebar.markdown("### 📥 Step 1: Upload your Dataset")
    uploaded_file = st.sidebar.file_uploader("CSV Files are accepted", type=["csv"])

    # Reset cleaning options if a new file is uploaded
    if uploaded_file is not None and "last_uploaded" not in st.session_state:
        st.session_state["last_uploaded"] = uploaded_file.name
        reset_cleaning_options()
    elif uploaded_file is not None and uploaded_file.name != st.session_state.get("last_uploaded"):
        st.session_state["last_uploaded"] = uploaded_file.name
        reset_cleaning_options()

    # ---------------------------
    # If file uploaded
    # ---------------------------
    if uploaded_file:
        df = pd.read_csv(uploaded_file)

        # Save original stats
        rows_before = int(len(df))
        nulls_before = int(df.isnull().sum().sum())
        duplicates_before = int(df.duplicated().sum())

        # Step 2: Options
        st.sidebar.markdown("### ⚙️ Step 2: Choose Cleaning Options")
        st.sidebar.caption("Select all options that apply to your dataset. Hover over each ❓ for guidance.")
        fill_method = st.sidebar.selectbox(
            "Missing Values",
            ["Fill with N/A", "Fill with Mean", "Fill with Median", "Fill by most common", "Drop Rows"],
             key="fill_method",
             help=("💡 Tip: For small datasets, filling values is better. If your dataset is big, you can consider dropping the rows.")
        )

        with st.sidebar.expander("Advanced Options"):
            st.checkbox("Remove duplicates", key="do_duplicates",
                        help="Removes rows that are exact duplicates. Recommended if your dataset has repeated entries.")
            st.checkbox("Standardize column names", key="do_standardize_cols",
                        help="Converts column names to lowercase and replaces spaces with underscores for consistency.")
            st.checkbox("Normalize text", key="do_normalize_text",
                        help="Makes text consistent (e.g., 'new york' → 'New York'). Skips emails automatically.")
            st.checkbox("Fix date formats", key="do_fix_dates",
                        help="Converts different date styles (e.g., '01/02/23', 'Feb 1, 2023') into YYYY-MM-DD format.")
            st.checkbox("Validate emails", key="do_validate_emails",
                        help="Ensures all emails follow a proper format. Invalid ones become `invalid@example.com`.")
            st.checkbox("Fuzzy standardize values", key="do_fuzzy_standardize",
                        help="Groups similar text values together (e.g., 'NYC', 'New York City', 'N.Y.C.' → 'NYC').")
            st.checkbox("Detect anomalies", key="do_anomaly_detection",
                        help="Flags unusual numeric values using statistical detection. Useful for spotting outliers (extreme values).")

    
        # Tabs for Raw vs Cleaned data
        with tab1:
            st.dataframe(df.head(10))

            # Optional Dataset Details
            with st.expander("Show Dataset Details"):
                st.markdown("**Column Info:**")
                st.caption("This table shows each column in the dataset along with its detected data type.")
                table_md = "| Column | Data Type |\n|--------|-----------|\n"
                for col in df.columns:
                    table_md += f"| {col} | {df[col].dtype} |\n"
                st.markdown(table_md)

                st.markdown("**Summary Statistics:**")
                st.caption(
                     """
                    This table provides descriptive statistics for each column in the dataset:

                    - **Numerical columns** (numbers) show: count, mean, standard deviation, minimum, maximum, and percentiles.
                    - **Categorical columns** (labels or text) show: count, number of unique values, most frequent value (*top*), and its frequency.
                    """, unsafe_allow_html=True
                )
                st.dataframe(df.describe(include="all").transpose())

        # Step 3: Run Cleaning
        st.sidebar.markdown("#### 🧹 Step 3: Apply Cleaning")
        if st.sidebar.button("Run Cleaning"):
            # Custom CSS for Loader
            loader_css = st.empty()
            loader_css.markdown("""
                <div id="loading-overlay" style="
                    position: fixed;
                    top: 0; left: 0;
                    width: 100vw; height: 100vh;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    background-color: rgba(255,255,255,0.95);
                    font-size: 42px;
                    font-weight: bold;
                    color: #2E86C1;
                    z-index: 99999;
                ">
                    <div style="margin-bottom: 30px;"> Cleaning in progress, please wait.
                    </div>
                    <div class="loader"></div>
                </div>

                <style>
                /* Spinner animation */
                .loader {
                    border: 14px solid #f3f3f3;
                    border-top: 14px solid #2E86C1;
                    border-radius: 50%;
                    width: 120px;
                    height: 120px;
                    animation: spin 1s linear infinite;
                }

                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
                </style>
            """, unsafe_allow_html=True)

            # Cleaning steps
            df_cleaned = df.copy()
            df_cleaned = fill_missing(df_cleaned, method=fill_method)

            if st.session_state["do_duplicates"]:
                df_cleaned.drop_duplicates(inplace=True)

            if st.session_state["do_standardize_cols"]:
                df_cleaned.columns = [c.strip().lower().replace(" ", "_") for c in df_cleaned.columns]

            if st.session_state["do_normalize_text"]:
                for col in df_cleaned.select_dtypes(include=["object"]).columns:
                    df_cleaned[col] = normalize_text(df_cleaned[col], col_name=col)

            if st.session_state["do_fix_dates"]:
                for col in df_cleaned.columns:
                    if "date" in col.lower():
                        df_cleaned[col] = standardize_dates(df_cleaned[col])

            if st.session_state["do_validate_emails"]:
                for col in df_cleaned.columns:
                    if "email" in col.lower():
                        df_cleaned[col] = validate_emails(df_cleaned[col])

            if st.session_state["do_fuzzy_standardize"]:
                for col in df_cleaned.select_dtypes(include=["object"]).columns:
                    df_cleaned[col] = fuzzy_standardize(df_cleaned[col], cutoff=0.85)

            anomalies = pd.DataFrame()
            if st.session_state["do_anomaly_detection"]:
                anomalies = detect_anomalies(df_cleaned)

            loader_css.empty()
            success_overlay = st.empty()

            (success_overlay.markdown("""
            <div style="
                position: fixed;
                top: 0; left: 0;
                width: 100vw; height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                background-color: rgba(255,255,255,0.95);
                font-size: 42px;
                font-weight: bold;
                color: #28A745;
                z-index: 99999;
            ">
                Cleaning Completed Successfully!
            </div>
            """, unsafe_allow_html=True))

            time.sleep(1)
            success_overlay.empty()

            with tab2:
                st.dataframe(df_cleaned.head(10))

            with tab3:
                if "anomalies" in locals() and not anomalies.empty:
                    rows_with_anomalies = anomalies.index.nunique()
                    st.warning(f"{rows_with_anomalies} rows contain anomalies ⚠️")
                    st.dataframe(anomalies)
                
                    # Recommendation for Anomalies
                    st.markdown("""
                    Anomalies are values in the dataset that are very different from the rest.
                    They can occur naturally such as rare but valid high values or from errors like incrorrect data entry or wrong units.
                
                    **How to Handle Anomalies:** 
                
                    These are suggested actions, but the final decision depends on the context of your dataset and your goals:
                    1. Review the flagged rows to understand why they appear unusual.  
                    2. Compare them with reliable references or source data.  
                    3. Possible actions:  
                        - Keep them if they are valid rare cases.  
                        - Correct them if they are clear errors.  
                        - Remove them if they are invalid and distort analysis.  
                    4. Document your decision so the cleaning process remains consistent and transparent.  
                    """)
                else:
                    rows_with_anomalies = 0
                    st.success("No anomalies detected ✅")

            # Save cleaned stats
            rows_after = int(len(df_cleaned))
            nulls_after = int(df_cleaned.isnull().sum().sum())
            duplicates_after = int(df_cleaned.duplicated().sum())
            anomalies_count = rows_with_anomalies

            # Compute deltas
            delta_rows = rows_after - rows_before
            delta_nulls = nulls_before - nulls_after
            delta_duplicates = duplicates_before - duplicates_after

            # Display status text
            def status_text(value, metric_type="neutral"):
                """
                metric_type options:
                - "good" : green (improvement, like duplicates/nulls fixed)
                - "bad"  : red (problem, like anomalies detected)
                - "neutral" : black (no change)
                """
                if value > 0:
                    if metric_type == "good":
                        return f"<span style='color:green;'>{abs(value)} fixed</span>"
                    elif metric_type == "bad":
                        return f"<span style='color:red;'>{abs(value)} detected</span>"
                    else:
                        return f"<span style='color:black;'>{abs(value)} added</span>"
                elif value < 0:
                    # Rare case if delta negative
                    return f"<span style='color:red;'>{abs(value)} changed</span>"
                else:
                    return "<span style='color:black;'>unchanged</span>"

            st.title("Summary")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                with st.container(border=True):
                    st.markdown("<div style='font-size:22px;'>Total Rows</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:40px;'>{rows_after}</div>", unsafe_allow_html=True)
                    st.markdown(status_text(delta_rows, metric_type="neutral"), unsafe_allow_html=True)
                    st.progress(rows_after / max(rows_before, 1))

            with col2:
                with st.container(border=True):
                    st.markdown("<div style='font-size:22px;'>Null Values</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:40px;'>{nulls_after}</div>", unsafe_allow_html=True)
                    st.markdown(status_text(delta_nulls, metric_type="good"), unsafe_allow_html=True)
                    st.progress(delta_nulls / max(nulls_before, 1) if nulls_before else 0)

            with col3:
                with st.container(border=True):
                    st.markdown("<div style='font-size:22px;'>Duplicates</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:40px;'>{duplicates_after}</div>", unsafe_allow_html=True)
                    st.markdown(status_text(delta_duplicates, metric_type="good"), unsafe_allow_html=True)
                    st.progress(delta_duplicates / max(duplicates_before, 1) if duplicates_before else 0)

            with col4:
                with st.container(border=True):
                    st.markdown("<div style='font-size:22px;'>Anomalies Detected</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:40px;'>{anomalies_count}</div>", unsafe_allow_html=True)
                    st.markdown(status_text(anomalies_count, metric_type="bad"), unsafe_allow_html=True)
                    st.progress(anomalies_count / max(rows_after, 1))

            # Step 4: Download
            st.subheader("📥 Step 4: Save")
            csv = df_cleaned.to_csv(index=False).encode("utf-8")
            st.download_button("Download Cleaned CSV", csv, "cleaned_data.csv", "text/csv")

    else:
        st.info(" Upload a CSV file in the sidebar to get started!")
