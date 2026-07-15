"""
auth.py
Simple session-based authentication helpers for the Streamlit app.
"""

import streamlit as st
import database as db


def login_screen():
    st.title("🔐 AI Customer Support — Login")
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Log In", type="primary"):
            user = db.verify_user(username, password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with tab_register:
        new_user = st.text_input("Choose a username", key="reg_user")
        new_pass = st.text_input("Choose a password", type="password", key="reg_pass")
        if st.button("Create Account"):
            if not new_user or not new_pass:
                st.warning("Please fill in both fields.")
            elif db.create_user(new_user, new_pass, role="user"):
                st.success("Account created! Please log in.")
            else:
                st.error("That username is already taken.")


def logout():
    st.session_state.user = None
    st.rerun()


def require_login():
    if "user" not in st.session_state:
        st.session_state.user = None
    if st.session_state.user is None:
        login_screen()
        st.stop()
