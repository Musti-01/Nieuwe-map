from workforce.i18n import tr, translated_formatter, translated_table
import streamlit as st


def clear_signin():
    language = st.session_state.get('language', 'nl')
    st.session_state.clear()
    st.session_state['language'] = language


def account_links(api, token, run):
    reset = st.query_params.get('reset')
    invite = st.query_params.get('invite')
    if reset:
        st.subheader(tr('Nieuw wachtwoord instellen'))
        with st.form('reset_password'):
            password = st.text_input(tr('Nieuw wachtwoord (minimaal 12 tekens)'), type='password')
            confirm = st.text_input(tr('Herhaal nieuw wachtwoord'), type='password')
            if st.form_submit_button(tr('Nieuw wachtwoord opslaan')):
                if password != confirm:
                    st.error(tr('De wachtwoorden komen niet overeen.'))
                elif run(lambda: api.reset_password(reset, password)):
                    clear_signin()
                    st.query_params.clear()
                    st.session_state['notice']='Wachtwoord hersteld. Log opnieuw in.'
                    st.rerun()
        st.stop()
    if invite:
        st.subheader(tr('Uitnodiging voor een vestiging'))
        st.caption(tr('Een uitnodiging geeft alleen medewerkersrechten. De link is 7 dagen geldig en eenmalig te gebruiken.'))
        existing = st.checkbox(tr('Ik heb al een ShiftFlow-account'), value=bool(token))
        if existing and not token:
            st.info(tr('Log hieronder in met het e-mailadres waarop je bent uitgenodigd. Daarna kun je de uitnodiging accepteren.'))
            return
        with st.form('accept_invitation'):
            name = None
            password = None
            confirm = None
            if not token:
                name=st.text_input(tr('Jouw volledige naam'))
                password=st.text_input(tr('Kies een wachtwoord (minimaal 12 tekens)'),type='password')
                confirm=st.text_input(tr('Herhaal gekozen wachtwoord'),type='password')
            if st.form_submit_button(tr('Uitnodiging accepteren')):
                if not token and password!=confirm:
                    st.error(tr('De wachtwoorden komen niet overeen.'))
                elif run(lambda: api.accept_invite(invite,token,name,password,language=st.session_state.get("language","nl"))):
                    st.query_params.clear()
                    st.session_state['notice']='Uitnodiging geaccepteerd. Log in om je vestiging te openen.' if not token else 'Je bent gekoppeld aan de vestiging.'
                    st.rerun()
        st.stop()


def password_settings(api, token, run):
    with st.expander(tr('Mijn wachtwoord wijzigen')):
        with st.form('change_password'):
            current=st.text_input(tr('Huidig wachtwoord'),type='password')
            new=st.text_input(tr('Nieuw persoonlijk wachtwoord'),type='password')
            confirm=st.text_input(tr('Herhaal persoonlijk wachtwoord'),type='password')
            if st.form_submit_button(tr('Wachtwoord wijzigen')):
                if new!=confirm:
                    st.error(tr('De wachtwoorden komen niet overeen.'))
                elif run(lambda: api.change_password(token,current,new)):
                    clear_signin()
                    st.session_state['notice']='Wachtwoord gewijzigd. Log opnieuw in; eerdere sessies zijn ingetrokken.'
                    st.rerun()


def invitations(api, token, branch_id, run, expanded=False):
    with st.expander(tr('Nieuwe medewerker uitnodigen'), expanded=expanded):
        st.write(tr('Maak een eenmalige uitnodigingslink voor een medewerker. Je kunt de link zelf delen; e-mail staat in de verzendwachtrij.'))
        with st.form(f'invite_{branch_id}'):
            email=st.text_input(tr('E-mailadres nieuwe medewerker'))
            if st.form_submit_button(tr('Uitnodiging maken')):
                link=run(lambda: api.invite(token,branch_id,email))
                if link:
                    st.session_state[f'invitation_link_{branch_id}']=link
        link=st.session_state.get(f'invitation_link_{branch_id}')
        if link:
            st.code(link,language=None)
            st.caption(tr('Deel deze link alleen met de bedoelde medewerker. Geldig voor 7 dagen; een nieuwe uitnodiging maakt de vorige link voor dit adres ongeldig.'))


def account_management(api, token, run):
    accounts = run(lambda: api.accounts(token))
    if accounts is None:
        return
    archived = st.toggle(tr('Verwijderde vestigingen tonen'), key='account_archived_branches')
    branches = run(lambda: api.platform_branches(token, archived=archived))
    if branches is None:
        return
    scope = st.session_state.get('account_branch_id')
    selected_branch = next((b for b in branches if b['id'] == scope), None)
    if scope != 'unassigned' and selected_branch is None:
        scope = None
        st.session_state.pop('account_branch_id', None)
        st.session_state.pop('managed_account_id', None)

    def select_branch(branch_id):
        st.session_state['account_branch_id'] = branch_id
        st.session_state.pop('managed_account_id', None)
        st.session_state.pop('account_search', None)
        st.session_state.pop('account_filter', None)

    if scope is None:
        st.write(tr('Klik op een vestiging om de gebruikers te bekijken.'))
        with st.container(key='sf_branch_cards'):
            for offset in range(0, len(branches), 2):
                for col, branch in zip(st.columns(2), branches[offset:offset+2]):
                    count = sum(branch['id'] in u['branch_ids'] for u in accounts)
                    with col.container(border=True, key=f"sf_card_branch_{branch['id']}"):
                        st.caption(branch['organization'])
                        st.subheader(branch['name'])
                        st.caption(tr('Gebruikers: {v0}', v0=count))
                        st.button(tr('Gebruikers'), key=f"account_branch_{branch['id']}",
                                  on_click=select_branch, args=(branch['id'],),
                                  icon=':material/arrow_forward:', use_container_width=True)
        count = sum(not u['branch_ids'] for u in accounts)
        st.button(tr('Zonder vestiging') + f' ({count})', key='account_branch_unassigned',
                  on_click=select_branch, args=('unassigned',), icon=':material/person_off:', use_container_width=True)
        return

    st.button(tr('Terug naar vestigingen'), on_click=select_branch, args=(None,))
    st.subheader(tr('Zonder vestiging') if scope == 'unassigned' else selected_branch['organization'] + ' · ' + selected_branch['name'])
    st.write(tr('Zoek de juiste persoon en klik op Beheren. Deactiveren stopt toegang en bewaart uren. Alleen een ongebruikt account kan definitief verwijderd worden.'))
    accounts = [u for u in accounts if not u['branch_ids']] if scope == 'unassigned' else [u for u in accounts if scope in u['branch_ids']]
    def clear_selection():
        st.session_state.pop('managed_account_id', None)
    search = st.text_input(tr('Zoek op naam of e-mailadres'), placeholder=tr('Bijvoorbeeld: test123'), key='account_search', on_change=clear_selection).strip().casefold()
    status = st.selectbox(tr('Toon accounts'), ['Alle accounts', 'Actief', 'Inactief'], key='account_filter', on_change=clear_selection, format_func=tr)
    visible = [u for u in accounts if (not search or search in u['naam'].casefold() or search in u['email'].casefold()) and (status == 'Alle accounts' or u['actief'] == (status == 'Actief'))]
    if not visible:
        st.info(tr('Geen accounts gevonden. Pas je zoekopdracht of filter aan.'))
    for user in visible:
        with st.container(border=True, key=f"sf_card_user_{user['id']}"):
            person, state, action = st.columns([3, 1, 1])
            with person:
                st.text(user['naam'])
                st.caption(user['email'])
                if user['platformeigenaar']:
                    st.caption(tr('Platformeigenaar · beschermd account'))
                elif user['platformbeheerder']:
                    st.caption(tr('Platformbeheerder'))
                if not user['can_manage']:
                    st.caption(tr(user['manage_reason']))
            with state:
                st.badge(tr('Actief') if user['actief'] else tr('Inactief'), color='green' if user['actief'] else 'gray')
            if action.button((tr('Beheren') if user['can_manage'] else tr('Bekijken')), key=f"manage_user_{user['id']}", use_container_width=True):
                st.session_state['managed_account_id'] = user['id']
    uid = st.session_state.get('managed_account_id')
    target = next((u for u in visible if u['id'] == uid), None)
    if target is None:
        st.info(tr('Kies hierboven eerst de persoon die je wilt beheren.'))
        return
    st.divider()
    st.subheader((tr('Account: ') + target['naam']))
    st.text(target['email'])
    if not target['can_manage']:
        st.info(tr(target['manage_reason']))
        return
    if target['actief']:
        st.write(tr('Deactiveren: deze persoon kan nergens meer inloggen. Lopende diensten worden afgesloten; uren blijven bewaard.'))
    else:
        st.write(tr('Heractiveren: deze persoon kan weer inloggen met de bestaande vestigingsrechten.'))
    with st.form(f'account_status_{uid}'):
        reason = st.text_input(tr('Reden voor accountwijziging'), value=tr('Toegang gewijzigd door platformbeheerder'), max_chars=300)
        if st.form_submit_button((tr('Account deactiveren') if target['actief'] else tr('Account heractiveren'))):
            if run(lambda: api.set_account_active(token, uid, not target['actief'], reason), 'Accountstatus gewijzigd.'):
                st.rerun()
    if target['can_delete']:
        with st.expander(tr('Ongebruikt account definitief verwijderen')):
            st.warning(tr('Dit verwijdert het account en eventuele vestigingskoppelingen. Dit kan niet ongedaan worden gemaakt. Gebruik deactiveren als je alleen toegang wilt stoppen.'))
            with st.form(f'delete_account_{uid}'):
                confirmed = st.checkbox(tr('Ja, verwijder dit ongebruikte account definitief'))
                if st.form_submit_button(tr('Account definitief verwijderen')):
                    if not confirmed:
                        st.error(tr('Bevestig eerst dat je dit account definitief wilt verwijderen.'))
                    elif run(lambda: api.delete_unused_account(token, uid), 'Het ongebruikte account is definitief verwijderd.'):
                        st.session_state.pop('managed_account_id', None)
                        st.rerun()
    else:
        st.caption(tr(target['delete_reason']))
