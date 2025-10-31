#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import hashlib
import sqlite3
import io
import difflib

st.set_page_config(page_title="Raw to Ready", page_icon="🧹", layout="wide")

# -------------------------------
# DATABASE FUNCTIONS
# -------------------------------
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
)
''')
conn.commit()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(username, email, password):
    c.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
              (username, email, hash_password(password)))
    conn.commit()


def login_user(email, password):
    c.execute("SELECT * FROM users WHERE email=? AND password_hash=?", (email, hash_password(password)))
    return c.fetchone()


# -------------------------------
# SESSION STATE INIT
# -------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "df_raw" not in st.session_state:
    st.session_state.df_raw = None
if "df_clean" not in st.session_state:
    st.session_state.df_clean = None


# -------------------------------
# NAVIGATION
# -------------------------------
st.sidebar.image("logonobg.png", use_container_width=True)
menu = st.sidebar.radio("Navigation", ["Home", "Login / Register"])

# -------------------------------
# LOGIN / REGISTER PAGE
# -------------------------------
if menu == "Login / Register":
    st.markdown("## 🔐 Login / Register")
    col_login, col_register = st.columns(2)

    with col_login:
        with st.container(border=True):
            st.markdown("### Login")
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            if st.button("Login"):
                user = login_user(login_email, login_password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.username = user[1]
                    st.success(f"Welcome back, {user[1]}!")
                else:
                    st.error("Invalid email or password.")

    with col_register:
        with st.container(border=True):
            st.markdown("### Register")
            reg_username = st.text_input("Username", key="register_username")
            reg_email = st.text_input("Email", key="register_email")
            reg_password = st.text_input("Password", type="password", key="register_password")
            reg_confirm = st.text_input("Confirm Password", type="password", key="register_confirm")

            if st.button("Register"):
                if reg_password != reg_confirm:
                    st.error("Passwords do not match.")
                elif not reg_username or not reg_email or not reg_password:
                    st.warning("Please fill out all fields.")
                else:
                    try:
                        register_user(reg_username, reg_email, reg_password)
                        st.success("Registration successful! You can now log in.")
                    except sqlite3.IntegrityError:
                        st.error("Email already registered. Please log in.")

# -------------------------------
# HOME PAGE
# -------------------------------
elif menu == "Home":
    if not st.session_state.logged_in:
        st.warning("Please log in to access the cleaning tool.")
        st.stop()

    st.markdown(f"### 👋 Welcome, {st.session_state.username}!")

    st.markdown("""
    <p style='font-size:15px; line-height:1.6;'>
     Welcome to <b>Raw to Ready!</b> Upload your CSV, choose what to fix, and download your clean dataset.
    </p>
    """, unsafe_allow_html=True)

    # --- SIDEBAR OPTIONS ---
    st.sidebar.markdown("### 📥 Step 1: Upload your Dataset")
    uploaded_file = st.sidebar.file_uploader("CSV Files are accepted", type=["csv"])

    st.sidebar.markdown("### ⚙️ Step 2: Choose Cleaning Options")
    missing_choice = st.sidebar.selectbox(
        "Handle Missing Values",
        ["None", "Fill with N/A", "Fill with Mean", "Fill with Median", "Fill by most common", "Drop Rows"]
    )

    with st.sidebar.expander("Advanced Options"):
        remove_dupes = st.checkbox("Remove duplicates")
        standardize_cols = st.checkbox("Standardize column names")
        normalize_text = st.checkbox("Normalize text")
        fix_dates = st.checkbox("Fix date formats")
        validate_emails = st.checkbox("Validate emails")
        fuzzy_standardize = st.checkbox("Fuzzy standardize values")
        detect_anomalies = st.checkbox("Detect anomalies")

    run_cleaning = st.sidebar.button("Run Cleaning")

    # --- FILE UPLOAD ---
    if uploaded_file is not None:
        try:
            st.session_state.df_raw = pd.read_csv(uploaded_file)
            st.success("✅ File uploaded successfully!")
        except Exception as e:
            st.error(f"Error reading file: {e}")

    # --- CLEANING FUNCTION ---
    if run_cleaning and st.session_state.df_raw is not None:
        df = st.session_state.df_raw.copy()

        # Handle Missing Values
        if missing_choice != "None":
            if missing_choice == "Fill with N/A":
                df = df.fillna("N/A")
            elif missing_choice == "Fill with Mean":
                df = df.fillna(df.mean(numeric_only=True))
            elif missing_choice == "Fill with Median":
                df = df.fillna(df.median(numeric_only=True))
            elif missing_choice == "Fill by most common":
                df = df.apply(lambda x: x.fillna(x.mode()[0]) if not x.mode().empty else x)
            elif missing_choice == "Drop Rows":
                df = df.dropna()

        # Advanced Cleaning
        if remove_dupes:
            df = df.drop_duplicates()

        if standardize_cols:
            df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

        if normalize_text:
            for col in df.select_dtypes(include="object"):
                if "email" not in col:
                    df[col] = df[col].astype(str).str.strip().str.capitalize()

        if fix_dates:
            for col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col], errors="ignore").dt.strftime("%Y-%m-%d")
                except Exception:
                    pass

        if validate_emails:
            for col in df.columns:
                if "email" in col:
                    df[col] = df[col].apply(lambda x: x if isinstance(x, str) and "@" in x else "invalid@email.com")

        if fuzzy_standardize:
            for col in df.select_dtypes(include="object"):
                unique_vals = df[col].dropna().unique()
                mapping = {}
                for val in unique_vals:
                    close = difflib.get_close_matches(val, unique_vals, n=1, cutoff=0.8)
                    if close:
                        mapping[val] = close[0]
                df[col] = df[col].replace(mapping)

        # Simple Anomaly Detection (numeric outliers)
        if detect_anomalies:
            numeric_cols = df.select_dtypes(include="number")
            anomalies = pd.DataFrame()
            for col in numeric_cols:
                mean, std = df[col].mean(), df[col].std()
                outliers = df[(df[col] > mean + 3*std) | (df[col] < mean - 3*std)]
                if not outliers.empty:
                    anomalies = pd.concat([anomalies, outliers])
            st.session_state.anomalies = anomalies
        else:
            st.session_state.anomalies = pd.DataFrame({"Note": ["No anomalies detected."]})

        st.session_state.df_clean = df
        st.success("✅ Cleaning complete!")

    # --- TABS ---
    tab1, tab2, tab3 = st.tabs(["Raw Data Preview", "Cleaned Data Preview", "Anomalies Detected"])
    with tab1:
        st.markdown("### Raw Data Preview")
        if st.session_state.df_raw is not None:
            st.dataframe(st.session_state.df_raw.head())
        else:
            st.info("Upload a CSV to preview data.")

    with tab2:
        st.markdown("### Cleaned Data Preview")
        if st.session_state.df_clean is not None:
            st.dataframe(st.session_state.df_clean.head())
        else:
            st.info("Run cleaning to view results.")

    with tab3:
        st.markdown("### Anomalies Detected")
        if "anomalies" in st.session_state:
            st.dataframe(st.session_state.anomalies)
        else:
            st.info("Run cleaning to check for anomalies.")

    # --- SUMMARY REPORT ---
    st.markdown("---")
    st.markdown("## Summary Report")

    if st.session_state.df_clean is not None:
        df = st.session_state.df_clean
        total_rows = len(df)
        null_values = df.isnull().sum().sum()
        duplicates = df.duplicated().sum()
        anomalies_count = len(st.session_state.anomalies) if "anomalies" in st.session_state else 0

        col1, col2, col3, col4 = st.columns(4)
        stats = {
            "Total Rows": total_rows,
            "Null Values": null_values,
            "Duplicates": duplicates,
            "Anomalies": anomalies_count
        }

        for i, (label, value) in enumerate(stats.items(), 1):
            with eval(f"col{i}"):
                with st.container(border=True):
                    st.markdown(f"<div style='font-size:22px;'>{label}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:40px;'>{value}</div>", unsafe_allow_html=True)
                    st.progress(min(1.0, value / total_rows if total_rows > 0 else 0))
    else:
        st.info("Run cleaning to view summary statistics.")

    # --- DOWNLOAD CLEANED FILE ---
    if st.session_state.df_clean is not None:
        buffer = io.StringIO()
        st.session_state.df_clean.to_csv(buffer, index=False)
        st.download_button(
            label="⬇️ Download Cleaned CSV",
            data=buffer.getvalue(),
            file_name="cleaned_data.csv",
            mime="text/csv"
        )
