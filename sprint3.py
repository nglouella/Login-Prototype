#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import io

# =========================
# CONFIGURATION
# =========================
st.set_page_config(page_title="Raw to Ready", page_icon="🧹", layout="wide")

# --- DATABASE SETUP ---
conn = sqlite3.connect("users.db")
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users (
                username TEXT,
                email TEXT UNIQUE,
                password TEXT
            )""")
conn.commit()

# --- HELPER FUNCTIONS ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(email, password):
    c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, hash_password(password)))
    return c.fetchone()

def add_user(username, email, password):
    try:
        c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                  (username, email, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

# --- SESSION STATE ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

# --- SIDEBAR LOGO + NAV ---
st.sidebar.image("logonobg.png", use_container_width=True)
menu = st.sidebar.radio("Navigation", ["Home", "Login / Register"])

# =========================
# LOGIN / REGISTER PAGE
# =========================
if menu == "Login / Register":
    st.markdown("---")
    st.markdown("## Login / Register")

    col_login, col_register = st.columns(2)

    # --- LOGIN ---
    with col_login:
        with st.container(border=True):
            st.markdown("### 🔐 Login")
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            if st.button("Login", key="login_button"):
                user = verify_user(login_email, login_password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user = user[0]
                    st.success(f"Welcome back, {user[0]}!")
                else:
                    st.error("Invalid email or password.")

    # --- REGISTER ---
    with col_register:
        with st.container(border=True):
            st.markdown("### 🧾 Register")
            reg_username = st.text_input("Username", key="register_username")
            reg_email = st.text_input("Email", key="register_email")
            reg_password = st.text_input("Password", type="password", key="register_password")
            reg_confirm = st.text_input("Confirm Password", type="password", key="register_confirm")

            if st.button("Register", key="register_button"):
                if reg_password != reg_confirm:
                    st.error("Passwords do not match.")
                elif add_user(reg_username, reg_email, reg_password):
                    st.success("Registration successful! You can now log in.")
                else:
                    st.warning("Email already registered.")

# =========================
# HOME PAGE + CLEANING TOOL
# =========================
elif menu == "Home":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("logo.png", use_container_width=False)

    st.markdown("""
    <p style='font-size:15px; line-height:1.6;'>
     Welcome to <b>Raw to Ready!</b> This tool makes data cleaning super simple —
     just upload your CSV, choose what you’d like to fix, and you’ll have a clean dataset ready for use.
    </p>
    """, unsafe_allow_html=True)

    if not st.session_state.logged_in:
        st.warning("Please log in to access the data cleaning tools.")
        st.stop()

    st.markdown(f"### 👋 Welcome, {st.session_state.user}!")

    # --- SIDEBAR CLEANING OPTIONS ---
    st.sidebar.markdown("### 📥 Step 1: Upload your Dataset")
    uploaded_file = st.sidebar.file_uploader("CSV Files are accepted", type=["csv"])

    st.sidebar.markdown("### ⚙️ Step 2: Choose Cleaning Options")
    st.sidebar.caption("Select all options that apply. Hover over ❓ icons for tips.")

    missing_option = st.sidebar.selectbox(
        "Missing Values",
        ["Fill with N/A", "Fill with Mean", "Fill with Median", "Fill by most common", "Drop Rows"],
        help="💡 Tip: For small datasets, filling values is better. For large datasets, consider dropping rows."
    )

    with st.sidebar.expander("Advanced Options"):
        remove_dup = st.checkbox("Remove duplicates", help="Removes exact duplicate rows.")
        std_colnames = st.checkbox("Standardize column names", help="Makes column names lowercase with underscores.")
        normalize_txt = st.checkbox("Normalize text", help="Standardizes capitalization except for email fields.")
        fix_dates = st.checkbox("Fix date formats", help="Converts date formats to YYYY-MM-DD.")
        validate_emails = st.checkbox("Validate emails", help="Replaces invalid emails with placeholder.")
        fuzzy_std = st.checkbox("Fuzzy standardize values", help="Groups similar text values together.")
        detect_anom = st.checkbox("Detect anomalies", help="Flags unusual numeric values (outliers).")

    st.sidebar.markdown("#### Step 3: Apply Cleaning")
    run_cleaning = st.sidebar.button("Run Cleaning")

    # --- TABS ---
    tab1, tab2, tab3 = st.tabs(["Raw Data Preview", "Cleaned Data Preview", "Anomalies Detected"])

    if uploaded_file:
        df = pd.read_csv(uploaded_file)

        with tab1:
            st.markdown("### Raw Data Preview")
            st.dataframe(df.head())

        if run_cleaning:
            cleaned_df = df.copy()

            # Apply cleaning operations
            if remove_dup:
                cleaned_df = cleaned_df.drop_duplicates()

            if std_colnames:
                cleaned_df.columns = cleaned_df.columns.str.lower().str.replace(" ", "_")

            if normalize_txt:
                for col in cleaned_df.select_dtypes(include="object"):
                    cleaned_df[col] = cleaned_df[col].str.strip().str.capitalize()

            if fix_dates:
                for col in cleaned_df.columns:
                    if "date" in col.lower():
                        cleaned_df[col] = pd.to_datetime(cleaned_df[col], errors="coerce").dt.strftime("%Y-%m-%d")

            with tab2:
                st.markdown("### Cleaned Data Preview")
                st.dataframe(cleaned_df.head())

            with tab3:
                st.markdown("### Anomalies Detected")
                st.dataframe(pd.DataFrame({"Report": ["No anomalies detected (demo)"]}))

            # --- SUMMARY REPORT ---
            st.markdown("---")
            st.markdown("## Summary Report")
            col1, col2, col3, col4 = st.columns(4)
            for label, val in zip(["Total Rows", "Null Values", "Duplicates", "Anomalies"],
                                  [len(cleaned_df), cleaned_df.isnull().sum().sum(), df.duplicated().sum(), 0]):
                with eval(f"col{['Total Rows','Null Values','Duplicates','Anomalies'].index(label)+1}"):
                    with st.container(border=True):
                        st.markdown(f"<div style='font-size:22px;'>{label}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:40px;'>{val}</div>", unsafe_allow_html=True)
                        st.progress(0)

            # --- DOWNLOAD BUTTON ---
            csv = cleaned_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Cleaned CSV", data=csv, file_name="cleaned_data.csv")

        else:
            st.info("Adjust your cleaning options and click **Run Cleaning** to see results.")
    else:
        st.info("Upload a CSV file to begin cleaning.")
