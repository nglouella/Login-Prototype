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

# Load config if exists
if os.path.exists(".streamlit/config.toml"):
    config = toml.load(".streamlit/config.toml")

# ============================
# DATABASE SETUP (Person A)
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

def hash_password(pw): return hashlib.sha256(pw.encode()).hexdigest()

def register_user(username, email, pw):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, email, password_hash) VALUES (?,?,?)",
                  (username, email, hash_password(pw)))
        conn.commit(); return True
    except sqlite3.IntegrityError:
        return False
    finally: conn.close()

def login_user(email, pw):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=? AND password_hash=?",
              (email, hash_password(pw)))
    user = c.fetchone(); conn.close(); return user

init_db()

# ============================
# SESSION INITIALIZATION
# ============================
for key, val in {"logged_in": False, "username": "", "email": ""}.items():
    if key not in st.session_state: st.session_state[key] = val

# ============================
# LOGIN / REGISTER / PROFILE (Person A)
# ============================
def show_login():
    st.markdown("## 🔐 Login to Raw2Ready")
    with st.form("login_form"):
        email = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            user = login_user(email, pw)
            if user:
                st.session_state.update(
                    {"logged_in": True, "username": user[1], "email": user[2]}
                )
                st.success(f"Welcome back, {user[1]}!"); time.sleep(1); st.rerun()
            else: st.error("Invalid credentials.")

    st.info("Don’t have an account? Go to **Register** from sidebar.")

def show_register():
    st.markdown("## 📝 Register")
    with st.form("register_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        cpw = st.text_input("Confirm Password", type="password")
        if st.form_submit_button("Register"):
            if not all([username, email, pw, cpw]):
                st.warning("Please fill in all fields.")
            elif pw != cpw:
                st.error("Passwords do not match.")
            elif register_user(username, email, pw):
                st.success("Registration successful! You can now log in.")
            else:
                st.error("Username or email already exists.")

def show_profile():
    st.markdown("## 👤 My Profile")
    st.write(f"**Username:** {st.session_state['username']}")
    st.write(f"**Email:** {st.session_state['email']}")
    if st.button("Logout"):
        for k in ["logged_in", "username", "email"]:
            st.session_state[k] = "" if k != "logged_in" else False
        st.success("Logged out."); time.sleep(1); st.rerun()

# ============================
# CUSTOM THEME
# ============================
theme_css = """
<style>
body { background-color: #F4F6F6; }
.main-title {text-align:center;font-size:2.5em;font-weight:bold;color:#2E86C1;}
.subtitle {text-align:center;font-size:1.2em;color:#555;margin-bottom:30px;}
.report-card{padding:20px;border-radius:15px;background-color:#fff;
border-left:6px solid #2E86C1;box-shadow:0px 2px 8px rgba(0,0,0,0.05);text-align:center;}
.delta-positive{color:green}.delta-negative{color:red}.delta-neutral{color:black}
</style>
"""
st.markdown(theme_css, unsafe_allow_html=True)

# ============================
# HELPER FUNCTIONS (from original)
# ============================
def standardize_dates(series):
    def parse_date(x):
        for fmt in ("%Y-%m-%d","%d/%m/%y","%d/%m/%Y","%b %d, %Y","%Y.%m.%d"):
            try: return datetime.strptime(str(x), fmt).strftime("%Y-%m-%d")
            except: continue
        return x
    return series.apply(parse_date)

def normalize_text(series, col=""):
    return series.astype(str).str.strip().str.lower().str.title() if "email" not in col.lower() else series

def validate_emails(series):
    return series.apply(lambda x: x if re.match(r"[^@]+@[^@]+\.[^@]+", str(x)) else "invalid@example.com")

def fill_missing(df, method="Fill with N/A"):
    d = df.copy()
    for c in d.columns:
        if d[c].isnull().sum()>0:
            if method=="Drop Rows": d.dropna(inplace=True)
            elif method=="Fill with N/A": d[c].fillna("N/A", inplace=True)
            elif method=="Fill with Mean" and pd.api.types.is_numeric_dtype(d[c]):
                d[c].fillna(d[c].mean(), inplace=True)
            elif method=="Fill with Median" and pd.api.types.is_numeric_dtype(d[c]):
                d[c].fillna(d[c].median(), inplace=True)
            elif method=="Fill by most common": d[c].fillna(d[c].mode()[0], inplace=True)
    return d

def fuzzy_standardize(series, cutoff=0.85):
    series = series.astype(str).str.strip(); uniq = series.dropna().unique(); m={}
    for v in uniq:
        match = difflib.get_close_matches(v, m.keys(), n=1, cutoff=cutoff)
        m[v] = m[match[0]] if match else v
    return series.map(m)

def detect_anomalies(df, threshold=3):
    a = pd.DataFrame()
    for c in df.select_dtypes(include=[np.number]).columns:
        if df[c].std()==0: continue
        z = (df[c]-df[c].mean())/df[c].std()
        mask = np.abs(z)>threshold
        if mask.any():
            sub=df[mask].copy(); sub["Anomaly_Column"]=c; sub["Anomaly_Value"]=df[c][mask]
            a=pd.concat([a,sub])
    return a

def reset_cleaning_options():
    for k,v in {
        "do_duplicates":False,"do_standardize_cols":False,"do_normalize_text":False,
        "do_fix_dates":False,"do_validate_emails":False,"do_fuzzy_standardize":False,
        "do_anomaly_detection":False,"fill_method":"Fill with N/A","cleaned_ready":False
    }.items(): st.session_state[k]=v

# ============================
# MAIN NAVIGATION
# ============================
menu = st.sidebar.radio("Navigation", ["Home","Login","Register","Profile"])
if menu=="Login": show_login()
elif menu=="Register": show_register()
elif menu=="Profile":
    if st.session_state["logged_in"]: show_profile()
    else: st.warning("Please log in first.")
elif menu=="Home":
    # ---------------- Hero Section ----------------
    col1,col2,col3 = st.columns([1,2,1])
    with col2: st.image("logo.png", use_container_width=False)
    st.markdown("""
        <p style='font-size:15px;line-height:1.6;'>
        Welcome to <b>Raw to Ready!</b> Upload your CSV, select what to clean,
        and download a ready dataset. </p>""", unsafe_allow_html=True)

    if not st.session_state["logged_in"]:
        st.info("👋 You are in guest mode. Log in to save your cleaning history.")

    # ---------------- Sidebar Upload ----------------
    st.sidebar.image("logonobg.png", use_container_width=True)
    st.sidebar.markdown("### 📥 Step 1: Upload your Dataset")
    uploaded_file = st.sidebar.file_uploader("CSV Files only", type=["csv"])

    if uploaded_file is not None:
        if uploaded_file.size > 200*1024*1024:
            st.error("File too large (max 200 MB).")
        else:
            df = pd.read_csv(uploaded_file)
            rows_before, nulls_before, dups_before = len(df), df.isnull().sum().sum(), df.duplicated().sum()
            st.sidebar.markdown("### ⚙️ Step 2: Choose Cleaning Options")
            fill_method = st.sidebar.selectbox("Missing Values",
                ["Fill with N/A","Fill with Mean","Fill with Median","Fill by most common","Drop Rows"],
                key="fill_method")
            with st.sidebar.expander("Advanced Options"):
                st.checkbox("Remove duplicates", key="do_duplicates")
                st.checkbox("Standardize column names", key="do_standardize_cols")
                st.checkbox("Normalize text", key="do_normalize_text")
                st.checkbox("Fix date formats", key="do_fix_dates")
                st.checkbox("Validate emails", key="do_validate_emails")
                st.checkbox("Fuzzy standardize values", key="do_fuzzy_standardize")
                st.checkbox("Detect anomalies", key="do_anomaly_detection")

            tab1,tab2,tab3 = st.tabs(["Raw Data Preview","Cleaned Data Preview","Anomalies Detected"])
            with tab1: st.dataframe(df.head(10))

            st.sidebar.markdown("#### 🧹 Step 3: Apply Cleaning")
            if st.sidebar.button("Run Cleaning"):
                loader = st.empty()
                loader.markdown("<h3>Cleaning in progress...</h3>", unsafe_allow_html=True)
                dfc = fill_missing(df, fill_method)
                if st.session_state.do_duplicates: dfc.drop_duplicates(inplace=True)
                if st.session_state.do_standardize_cols:
                    dfc.columns=[c.strip().lower().replace(" ","_") for c in dfc.columns]
                if st.session_state.do_normalize_text:
                    for c in dfc.select_dtypes(include=["object"]).columns:
                        dfc[c]=normalize_text(dfc[c],c)
                if st.session_state.do_fix_dates:
                    for c in dfc.columns:
                        if "date" in c.lower(): dfc[c]=standardize_dates(dfc[c])
                if st.session_state.do_validate_emails:
                    for c in dfc.columns:
                        if "email" in c.lower(): dfc[c]=validate_emails(dfc[c])
                if st.session_state.do_fuzzy_standardize:
                    for c in dfc.select_dtypes(include=["object"]).columns:
                        dfc[c]=fuzzy_standardize(dfc[c])
                anomalies = detect_anomalies(dfc) if st.session_state.do_anomaly_detection else pd.DataFrame()
                loader.empty(); st.success("Cleaning Completed Successfully!")

                with tab2: st.dataframe(dfc.head(10))
                with tab3:
                    if not anomalies.empty:
                        st.warning(f"{anomalies.index.nunique()} rows contain anomalies ⚠️")
                        st.dataframe(anomalies)
                    else: st.success("No anomalies detected ✅")

                # Summary
                rows_after,len_nulls=len(dfc),dfc.isnull().sum().sum()
                st.title("Summary")
                col1,col2,col3,col4=st.columns(4)
                col1.metric("Total Rows",rows_after)
                col2.metric("Null Values",int(len_nulls),int(nulls_before-len_nulls))
                col3.metric("Duplicates",int(dfc.duplicated().sum()),int(dups_before-dfc.duplicated().sum()))
                col4.metric("Anomalies Detected",len(anomalies))
                csv=dfc.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download Cleaned CSV",csv,"cleaned_data.csv","text/csv")
    else:
        st.info("Upload a CSV file to start cleaning.")
