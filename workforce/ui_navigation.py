"""Navigation callbacks; services still authorize every action independently."""
import streamlit as st


def open_branch_page(branch_id, page):
    st.session_state[f'branch_page_{branch_id}'] = page


def open_shift_review(branch_id, entry_id):
    st.session_state[f'focus_review_{branch_id}'] = entry_id
    open_branch_page(branch_id, 'Shiften controleren')
