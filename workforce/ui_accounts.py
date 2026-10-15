import streamlit as st


def account_links(api, token, run):
    reset = st.query_params.get('reset')
    invite = st.query_params.get('invite')
    if reset:
        st.subheader('Nieuw wachtwoord instellen')
        with st.form('reset_password'):
            password = st.text_input('Nieuw wachtwoord (minimaal 12 tekens)', type='password')
            confirm = st.text_input('Herhaal nieuw wachtwoord', type='password')
            if st.form_submit_button('Nieuw wachtwoord opslaan'):
                if password != confirm:
                    st.error('De wachtwoorden komen niet overeen.')
                elif run(lambda: api.reset_password(reset, password)):
                    st.session_state.clear()
                    st.query_params.clear()
                    st.session_state['notice']='Wachtwoord hersteld. Log opnieuw in.'
                    st.rerun()
        st.stop()
    if invite:
        st.subheader('Uitnodiging voor een vestiging')
        st.caption('Een uitnodiging geeft alleen medewerkersrechten. De link is 7 dagen geldig en eenmalig te gebruiken.')
        existing = st.checkbox('Ik heb al een ShiftFlow-account', value=bool(token))
        if existing and not token:
            st.info('Log hieronder in met het e-mailadres waarop je bent uitgenodigd. Daarna kun je de uitnodiging accepteren.')
            return
        with st.form('accept_invitation'):
            name = None
            password = None
            confirm = None
            if not token:
                name=st.text_input('Jouw volledige naam')
                password=st.text_input('Kies een wachtwoord (minimaal 12 tekens)',type='password')
                confirm=st.text_input('Herhaal gekozen wachtwoord',type='password')
            if st.form_submit_button('Uitnodiging accepteren'):
                if not token and password!=confirm:
                    st.error('De wachtwoorden komen niet overeen.')
                elif run(lambda: api.accept_invite(invite,token,name,password)):
                    st.query_params.clear()
                    st.session_state['notice']='Uitnodiging geaccepteerd. Log in om je vestiging te openen.' if not token else 'Je bent gekoppeld aan de vestiging.'
                    st.rerun()
        st.stop()


def password_settings(api, token, run):
    with st.expander('Mijn wachtwoord wijzigen'):
        with st.form('change_password'):
            current=st.text_input('Huidig wachtwoord',type='password')
            new=st.text_input('Nieuw persoonlijk wachtwoord',type='password')
            confirm=st.text_input('Herhaal persoonlijk wachtwoord',type='password')
            if st.form_submit_button('Wachtwoord wijzigen'):
                if new!=confirm:
                    st.error('De wachtwoorden komen niet overeen.')
                elif run(lambda: api.change_password(token,current,new)):
                    st.session_state.clear()
                    st.session_state['notice']='Wachtwoord gewijzigd. Log opnieuw in; eerdere sessies zijn ingetrokken.'
                    st.rerun()


def invitations(api, token, branch_id, run):
    with st.expander('Nieuwe medewerker uitnodigen'):
        st.write('Maak een eenmalige uitnodigingslink voor een medewerker. Je kunt de link zelf delen; e-mail staat in de verzendwachtrij.')
        with st.form(f'invite_{branch_id}'):
            email=st.text_input('E-mailadres nieuwe medewerker')
            if st.form_submit_button('Uitnodiging maken'):
                link=run(lambda: api.invite(token,branch_id,email))
                if link:
                    st.session_state[f'invitation_link_{branch_id}']=link
        link=st.session_state.get(f'invitation_link_{branch_id}')
        if link:
            st.code(link,language=None)
            st.caption('Deel deze link alleen met de bedoelde medewerker. Geldig voor 7 dagen; een nieuwe uitnodiging maakt de vorige link voor dit adres ongeldig.')


def account_management(api, token, run):
    st.write('Zoek de juiste persoon en klik op Beheren. Deactiveren stopt toegang en bewaart uren. Alleen een ongebruikt account kan definitief verwijderd worden.')
    accounts = run(lambda: api.accounts(token))
    if accounts is None:
        return
    def clear_selection():
        st.session_state.pop('managed_account_id', None)
    search = st.text_input('Zoek op naam of e-mailadres', placeholder='Bijvoorbeeld: test123', key='account_search', on_change=clear_selection).strip().casefold()
    status = st.selectbox('Toon accounts', ['Alle accounts', 'Actief', 'Inactief'], key='account_filter', on_change=clear_selection)
    visible = [u for u in accounts if (not search or search in u['naam'].casefold() or search in u['email'].casefold()) and (status == 'Alle accounts' or u['actief'] == (status == 'Actief'))]
    if not visible:
        st.info('Geen accounts gevonden. Pas je zoekopdracht of filter aan.')
    for user in visible:
        with st.container(border=True):
            person, state, action = st.columns([3, 1, 1])
            with person:
                st.text(user['naam'])
                st.caption(user['email'])
                if user['platformeigenaar']:
                    st.caption('Platformeigenaar · beschermd account')
                elif user['platformbeheerder']:
                    st.caption('Platformbeheerder')
                if not user['can_manage']:
                    st.caption(user['manage_reason'])
            state.write('Actief' if user['actief'] else 'Inactief')
            if action.button('Beheren' if user['can_manage'] else 'Bekijken', key=f"manage_user_{user['id']}", use_container_width=True):
                st.session_state['managed_account_id'] = user['id']
    uid = st.session_state.get('managed_account_id')
    target = next((u for u in accounts if u['id'] == uid), None)
    if target is None:
        st.info('Kies hierboven eerst de persoon die je wilt beheren.')
        return
    st.divider()
    st.subheader('Account: ' + target['naam'])
    st.text(target['email'])
    if not target['can_manage']:
        st.info(target['manage_reason'])
        return
    if target['actief']:
        st.write('Deactiveren: deze persoon kan nergens meer inloggen. Lopende diensten worden afgesloten; uren blijven bewaard.')
    else:
        st.write('Heractiveren: deze persoon kan weer inloggen met de bestaande vestigingsrechten.')
    with st.form(f'account_status_{uid}'):
        reason = st.text_input('Reden voor accountwijziging', value='Toegang gewijzigd door platformbeheerder', max_chars=300)
        if st.form_submit_button('Account deactiveren' if target['actief'] else 'Account heractiveren'):
            if run(lambda: api.set_account_active(token, uid, not target['actief'], reason), 'Accountstatus gewijzigd.'):
                st.rerun()
    if target['can_delete']:
        with st.expander('Ongebruikt account definitief verwijderen'):
            st.warning('Dit verwijdert het account en eventuele vestigingskoppelingen. Dit kan niet ongedaan worden gemaakt. Gebruik deactiveren als je alleen toegang wilt stoppen.')
            with st.form(f'delete_account_{uid}'):
                confirmed = st.checkbox('Ja, verwijder dit ongebruikte account definitief')
                if st.form_submit_button('Account definitief verwijderen'):
                    if not confirmed:
                        st.error('Bevestig eerst dat je dit account definitief wilt verwijderen.')
                    elif run(lambda: api.delete_unused_account(token, uid), 'Het ongebruikte account is definitief verwijderd.'):
                        st.session_state.pop('managed_account_id', None)
                        st.rerun()
    else:
        st.caption(target['delete_reason'])
