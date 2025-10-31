#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import io
import numpy as np
import re
import difflib

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(page_title="Raw to Ready", page_icon="🧹", layout="wide")

# -------------------------
# DATABASE (for Login/Register)
# -------------------------
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT UNIQUE,
    password_hash TEXT
)
""")
conn.commit()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def add_user(username: str, email: str, password: str) -> bool:
    try:
        c.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                  (username, email, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(email: str, password: str):
    c.execute("SELECT username, email FROM users WHERE email=? AND password_hash=?", (email, hash_password(password)))
    return c.fetchone()  # None or tuple(username, email)

# -------------------------
# SESSION STATE INIT
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "df_raw" not in st.session_state:
    st.session_state.df_raw = None
if "df_clean" not in st.session_state:
    st.session_state.df_clean = None
if "anomalies" not in st.session_state:
    st.session_state.anomalies = None

# -------------------------
# LAYOUT (matching Sprint 2 UI)
# -------------------------
st.sidebar.image("logonobg.png", use_container_width=True)
menu = st.sidebar.radio("Navigation", ["Home", "Login / Register"])

# -------------------------
# HOME PAGE (with cleaning UI exactly like Sprint 2)
# -------------------------
if menu == "Home":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("logo.png", use_container_width=False)

    st.markdown("""
    <p style='font-size:15px; line-height:1.6;'>
     Welcome to <b>Raw to Ready!</b> This tool makes data cleaning super simple —
     just upload your CSV, choose what you’d like to fix, and you’ll have a clean dataset ready for use.
    </p>
    """, unsafe_allow_html=True)

    # If logged in show welcome & logout; otherwise show gentle note
    if st.session_state.logged_in:
        st.success(f"👋 Logged in as: {st.session_state.username}")
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.experimental_rerun()
    else:
        st.info("You may use the cleaning tools without signing in. (Signed-in cleaning will be saved to history in Sprint 4.)")

    # --- SIDEBAR OPTIONS (keep identical wording & helpers) ---
    st.sidebar.markdown("### 📥 Step 1: Upload your Dataset")
    uploaded_file = st.sidebar.file_uploader("CSV Files are accepted", type=["csv"])

    st.sidebar.markdown("### ⚙️ Step 2: Choose Cleaning Options")
    st.sidebar.caption("Select all options that apply. Hover over ❓ icons for tips.")

    # match keys so Streamlit keeps values between reruns
    missing_choice = st.sidebar.selectbox(
        "Missing Values",
        ["Fill with N/A", "Fill with Mean", "Fill with Median", "Fill by most common", "Drop Rows"],
        help="💡 Tip: For small datasets, filling values is better. For large datasets, consider dropping rows.",
        key="missing_choice"
    )

    with st.sidebar.expander("Advanced Options"):
        remove_duplicates = st.checkbox("Remove duplicates", help="Removes exact duplicate rows.", key="remove_duplicates")
        standardize_column_names = st.checkbox("Standardize column names", help="Makes column names lowercase with underscores.", key="standardize_column_names")
        normalize_text = st.checkbox("Normalize text", help="Standardizes capitalization except for email fields.", key="normalize_text")
        fix_date_formats = st.checkbox("Fix date formats", help="Converts date formats to YYYY-MM-DD.", key="fix_date_formats")
        validate_emails = st.checkbox("Validate emails", help="Replaces invalid emails with placeholder.", key="validate_emails")
        fuzzy_standardize = st.checkbox("Fuzzy standardize values", help="Groups similar text values together.", key="fuzzy_standardize")
        detect_anomalies = st.checkbox("Detect anomalies", help="Flags unusual numeric values (outliers).", key="detect_anomalies")

    st.sidebar.markdown("#### Step 3: Apply Cleaning")
    run_cleaning = st.sidebar.button("Run Cleaning", key="run_cleaning")

    # --- MAIN CONTENT TABS ---
    tab1, tab2, tab3 = st.tabs(["Raw Data Preview", "Cleaned Data Preview", "Anomalies Detected"])

    # --- LOAD UPLOADED FILE (if any) ---
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.session_state.df_raw = df.copy()
        except Exception as e:
            st.error(f"Error reading CSV: {e}")
            st.session_state.df_raw = None

    # Raw Data Preview tab
    with tab1:
        st.markdown("### Raw Data Preview")
        if st.session_state.df_raw is not None:
            st.dataframe(st.session_state.df_raw.head())
        else:
            st.info("Upload a CSV file to preview raw data.")

    # If user clicked run_cleaning, perform cleaning (works whether logged in or not)
    if run_cleaning:
        if st.session_state.df_raw is None:
            st.warning("Please upload a CSV before running cleaning.")
        else:
            df_work = st.session_state.df_raw.copy()

            # --- Missing values ---
            if missing_choice == "Fill with N/A":
                df_work = df_work.fillna("N/A")
            elif missing_choice == "Fill with Mean":
                for col in df_work.select_dtypes(include=[np.number]).columns:
                    df_work[col] = df_work[col].fillna(df_work[col].mean())
            elif missing_choice == "Fill with Median":
                for col in df_work.select_dtypes(include=[np.number]).columns:
                    df_work[col] = df_work[col].fillna(df_work[col].median())
            elif missing_choice == "Fill by most common":
                for col in df_work.columns:
                    try:
                        mode = df_work[col].mode(dropna=True)
                        if not mode.empty:
                            df_work[col] = df_work[col].fillna(mode[0])
                    except Exception:
                        pass
            elif missing_choice == "Drop Rows":
                df_work = df_work.dropna()

            # --- Advanced options ---
            if remove_duplicates:
                df_work = df_work.drop_duplicates()

            if standardize_column_names:
                df_work.columns = df_work.columns.str.strip().str.lower().str.replace(" ", "_")

            if normalize_text:
                for col in df_work.select_dtypes(include=["object"]).columns:
                    if "email" not in col.lower():
                        # Convert to sentence-case (capitalize first char) to match previous sprint behavior
                        df_work[col] = df_work[col].astype(str).str.strip().str.capitalize()

            if fix_date_formats:
                for col in df_work.columns:
                    # only attempt for likely date columns or object columns
                    if "date" in col.lower() or df_work[col].dtype == object:
                        try:
                            parsed = pd.to_datetime(df_work[col], errors="coerce")
                            # only convert if parsing yields some non-null values
                            if parsed.notna().any():
                                df_work[col] = parsed.dt.strftime("%Y-%m-%d")
                        except Exception:
                            pass

            if validate_emails:
                email_regex = re.compile(r"[^@]+@[^@]+\.[^@]+")
                for col in df_work.columns:
                    if "email" in col.lower():
                        df_work[col] = df_work[col].apply(lambda x: x if isinstance(x, str) and email_regex.match(x) else "invalid@email.com")

            if fuzzy_standardize:
                # Basic fuzzy standardization per text column
                for col in df_work.select_dtypes(include=["object"]).columns:
                    vals = pd.Series(df_work[col].dropna().unique())
                    mapping = {}
                    for v in vals:
                        # find the closest match among unique values (cutoff adjustable)
                        match = difflib.get_close_matches(v, vals, n=1, cutoff=0.85)
                        if match and match[0] != v:
                            mapping[v] = match[0]
                    if mapping:
                        df_work[col] = df_work[col].replace(mapping)

            # --- Simple anomaly detection (z-score method) ---
            anomalies_df = pd.DataFrame()
            if detect_anomalies:
                numeric_cols = df_work.select_dtypes(include=[np.number]).columns
                for col in numeric_cols:
                    col_mean = df_work[col].mean()
                    col_std = df_work[col].std()
                    if pd.notnull(col_std) and col_std > 0:
                        z_scores = (df_work[col] - col_mean) / col_std
                        outliers = df_work[np.abs(z_scores) > 3]
                        if not outliers.empty:
                            anomalies_df = pd.concat([anomalies_df, outliers])
                # drop duplicate rows in anomalies_df if multiple numeric columns flagged same row
                if not anomalies_df.empty:
                    anomalies_df = anomalies_df.drop_duplicates()
            else:
                anomalies_df = pd.DataFrame({"Anomaly Report": ["No anomalies detected (placeholder)"]})

            # Save results to session_state
            st.session_state.df_clean = df_work.copy()
            st.session_state.anomalies = anomalies_df.copy()

            st.success("✅ Cleaning complete! See Cleaned Data Preview and Anomalies Detected tabs.")

    # Cleaned Data Preview tab
    with tab2:
        st.markdown("### Cleaned Data Preview")
        if st.session_state.df_clean is not None:
            st.dataframe(st.session_state.df_clean.head())
        else:
            st.info("No cleaned data yet. Set options and click 'Run Cleaning' in the sidebar.")

    # Anomalies tab
    with tab3:
        st.markdown("### Anomalies Detected")
        if st.session_state.anomalies is not None:
            st.dataframe(st.session_state.anomalies.head(100))
        else:
            st.info("No anomalies to show. Run cleaning with 'Detect anomalies' checked to populate this tab.")

    # --- SUMMARY ---
    st.markdown("---")
    st.markdown("## Summary Report")
    col1, col2, col3, col4 = st.columns(4)

    # default zeros
    total_rows_val = 0
    null_values_val = 0
    duplicates_val = 0
    anomalies_val = 0

    if st.session_state.df_clean is not None:
        total_rows_val = len(st.session_state.df_clean)
        null_values_val = int(st.session_state.df_clean.isnull().sum().sum())
        # duplicates counted vs original upload
        if st.session_state.df_raw is not None:
            duplicates_val = int(st.session_state.df_raw.duplicated().sum())
        else:
            duplicates_val = int(st.session_state.df_clean.duplicated().sum())
        if isinstance(st.session_state.anomalies, pd.DataFrame):
            anomalies_val = len(st.session_state.anomalies) if not st.session_state.anomalies.empty else 0

    labels = ["Total Rows", "Null Values", "Duplicates", "Anomalies"]
    values = [total_rows_val, null_values_val, duplicates_val, anomalies_val]

    for i, (label, val) in enumerate(zip(labels, values), start=1):
        with eval(f"col{i}"):
            with st.container(border=True):
                st.markdown(f"<div style='font-size:22px;'>{label}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:40px;'>{val}</div>", unsafe_allow_html=True)
                # progress - if total_rows_val > 0, show proportion for nulls/duplicates
                if label == "Total Rows":
                    st.progress(1.0 if val > 0 else 0.0)
                else:
                    st.progress(min(1.0, val / total_rows_val) if total_rows_val > 0 else 0.0)

    # --- DOWNLOAD CLEANED CSV ---
    if st.session_state.df_clean is not None:
        buffer = io.StringIO()
        st.session_state.df_clean.to_csv(buffer, index=False)
        st.download_button("Download Cleaned CSV", data=buffer.getvalue(), file_name="cleaned_data.csv", mime="text/csv")
    else:
        # placeholder disabled download button (keeps UI consistent)
        st.download_button("Download Cleaned CSV", data=b"", file_name="cleaned_data.csv", disabled=True)

# -------------------------
# LOGIN / REGISTER PAGE (unchanged UI)
# -------------------------
else:
    st.markdown("---")
    st.markdown("## Login / Register")

    col_login, col_register = st.columns(2)

    with col_login:
        with st.container(border=True):
            st.markdown("### 🔐 Login")
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            if st.button("Login", key="login_button"):
                result = verify_user(login_email, login_password)
                if result:
                    st.session_state.logged_in = True
                    st.session_state.username = result[0]
                    st.success(f"Welcome back, {result[0]}!")
                else:
                    st.error("Invalid email or password.")

    with col_register:
        with st.container(border=True):
            st.markdown("### 🧾 Register")
            reg_username = st.text_input("Username", key="register_username")
            reg_email = st.text_input("Email", key="register_email")
            reg_password = st.text_input("Password", type="password", key="register_password")
            reg_confirm = st.text_input("Confirm Password", type="password", key="register_confirm")
            if st.button("Register", key="register_button"):
                if not reg_username or not reg_email or not reg_password:
                    st.warning("Please fill out all fields.")
                elif reg_password != reg_confirm:
                    st.error("Passwords do not match.")
                else:
                    ok = add_user(reg_username, reg_email, reg_password)
                    if ok:
                        st.success("Registration successful. You can now log in.")
                    else:
                        st.error("Email already registered. Try logging in or use another email.")
