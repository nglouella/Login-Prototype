#!/usr/bin/env python
# coding: utf-8

# In[ ]:


#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Raw to Ready", page_icon="🧹", layout="wide")

# --- SIDEBAR LOGO + NAV ---
st.sidebar.image("logonobg.png", use_container_width=True)
menu = st.sidebar.radio("Navigation", ["Home", "Login / Register"])

# Initialize session state
if "df_raw" not in st.session_state:
    st.session_state.df_raw = None
if "df_clean" not in st.session_state:
    st.session_state.df_clean = None

# --- HOME PAGE ---
if menu == "Home":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("logo.png", use_container_width=False)

    st.markdown("""
    <p style='font-size:15px; line-height:1.6;'>
     Welcome to <b>Raw to Ready!</b> This tool makes data cleaning simple — 
     just upload your CSV, choose what to fix, and you’ll have a clean dataset ready for use.
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

    remove_dupes = st.sidebar.checkbox("Remove duplicates", help="Removes exact duplicate rows.")
    standardize_cols = st.sidebar.checkbox("Standardize column names", help="Makes column names lowercase with underscores.")
    normalize_text = st.sidebar.checkbox("Normalize text", help="Standardizes capitalization except for email fields.")
    fix_dates = st.sidebar.checkbox("Fix date formats", help="Converts date formats to YYYY-MM-DD.")

    run_cleaning = st.sidebar.button("Run Cleaning")

    # --- FUNCTIONALITY: FILE UPLOAD ---
    if uploaded_file is not None:
        try:
            st.session_state.df_raw = pd.read_csv(uploaded_file)
            st.success("✅ File uploaded successfully!")
        except Exception as e:
            st.error(f"Error reading file: {e}")

    # --- FUNCTIONALITY: RUN CLEANING ---
    if run_cleaning and st.session_state.df_raw is not None:
        df = st.session_state.df_raw.copy()

        # 1. Handle Missing Values
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

        # 2. Remove Duplicates
        if remove_dupes:
            df = df.drop_duplicates()

        # 3. Standardize Column Names
        if standardize_cols:
            df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

        # 4. Normalize Text
        if normalize_text:
            for col in df.select_dtypes(include="object"):
                if "email" not in col:
                    df[col] = df[col].astype(str).str.strip().str.capitalize()

        # 5. Fix Date Formats
        if fix_dates:
            for col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col], errors="ignore").dt.strftime("%Y-%m-%d")
                except Exception:
                    pass

        # Save cleaned data
        st.session_state.df_clean = df
        st.success("✅ Cleaning complete!")

    # --- MAIN CONTENT ---
    tab1, tab2, tab3 = st.tabs(["Raw Data Preview", "Cleaned Data Preview", "Anomalies Detected"])

    with tab1:
        st.markdown("### Raw Data Preview")
        if st.session_state.df_raw is not None:
            st.dataframe(st.session_state.df_raw.head())
        else:
            st.info("Upload a CSV file to preview raw data.")

    with tab2:
        st.markdown("### Cleaned Data Preview")
        if st.session_state.df_clean is not None:
            st.dataframe(st.session_state.df_clean.head())
        else:
            st.info("Click 'Run Cleaning' to view cleaned data.")

    with tab3:
        st.markdown("### Anomalies Detected")
        st.dataframe(pd.DataFrame({"Anomaly Report": ["Anomaly detection feature coming in Sprint 4."]}))

    # --- SUMMARY REPORT ---
    st.markdown("---")
    st.markdown("## Summary Report")

    col1, col2, col3, col4 = st.columns(4)
    if st.session_state.df_clean is not None:
        df = st.session_state.df_clean
        total_rows = len(df)
        null_values = df.isnull().sum().sum()
        duplicates = df.duplicated().sum()
        anomalies = 0  # Placeholder until Sprint 4

        stats = {
            "Total Rows": total_rows,
            "Null Values": null_values,
            "Duplicates": duplicates,
            "Anomalies": anomalies
        }

        for i, (label, value) in enumerate(stats.items(), 1):
            with eval(f"col{i}"):
                with st.container(border=True):
                    st.markdown(f"<div style='font-size:22px;'>{label}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:40px;'>{value}</div>", unsafe_allow_html=True)
                    st.progress(min(1.0, value / total_rows if total_rows > 0 else 0))
    else:
        st.info("Run data cleaning to view summary statistics.")

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

# --- LOGIN / REGISTER PAGE ---
else:
    st.markdown("---")
    st.markdown("## Login / Register")

    col_login, col_register = st.columns(2)
    with col_login:
        with st.container(border=True):
            st.markdown("### 🔐 Login")
            st.text_input("Email", key="login_email")
            st.text_input("Password", type="password", key="login_password")
            st.button("Login", key="login_button")

    with col_register:
        with st.container(border=True):
            st.markdown("### 🧾 Register")
            st.text_input("Username", key="register_username")
            st.text_input("Email", key="register_email")
            st.text_input("Password", type="password", key="register_password")
            st.text_input("Confirm Password", type="password", key="register_confirm")
            st.button("Register", key="register_button")

