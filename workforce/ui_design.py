"""Shared visual shell; all dynamic HTML text is escaped."""
from html import escape
from pathlib import Path
import streamlit as st
from workforce.i18n import tr


def apply_design():
    css = Path(__file__).with_name('styles.css').read_text()
    st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)


def brand(sidebar=False):
    subtitle = escape(tr('Personeel & tijd · Eén platform voor al jouw vestigingen'))
    compact = ' sf-brand-compact' if sidebar else ''
    heading = 'div' if sidebar else 'h1'
    st.markdown(f'<div class="sf-brand{compact}"><span class="sf-logo" aria-hidden="true">SF</span>'
                f'<div><{heading} class="sf-wordmark">ShiftFlow</{heading}><div class="sf-tagline">{subtitle}</div></div></div>',
                unsafe_allow_html=True)


def welcome():
    heading = escape(tr('Je team. Je planning. Eén overzicht.'))
    description = escape(tr('Van de eerste geplande shift tot de laatste gewerkte minuut. Alles voor je vestiging op één plek.'))
    labels = [escape(tr(label)) for label in ('Planning', 'Werkuren', 'Afwezigheden')]
    chips = ''.join(f'<span>{label}</span>' for label in labels)
    st.markdown(f'<section class="sf-welcome"><div class="sf-eyebrow">SHIFTFLOW</div><h2>{heading}</h2>'
                f'<p>{description}</p><div class="sf-feature-list">{chips}</div>'
                '<div class="sf-clock" aria-hidden="true"><div class="sf-clock-hand"></div></div></section>',
                unsafe_allow_html=True)
