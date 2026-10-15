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
    st.write('Deactiveren blokkeert het volledige account, trekt sessies in en sluit lopende diensten af. Historische uren blijven bewaard. Heractiveren herstelt bestaande vestigingsrollen.')
    accounts=run(lambda: api.accounts(token))
    if not accounts:
        return
    st.dataframe([{k:v for k,v in row.items() if k!='id'} for row in accounts],hide_index=True,use_container_width=True)
    uid=st.selectbox('Account beheren',[u['id'] for u in accounts],format_func=lambda i: next(f"{u['naam']} · {u['email']} · {'Actief' if u['actief'] else 'Inactief'}" for u in accounts if u['id']==i))
    target=next(u for u in accounts if u['id']==uid)
    with st.form('account_status'):
        reason=st.text_input('Reden voor accountwijziging',max_chars=300)
        confirmed=st.checkbox('Ik bevestig deze wijziging van de volledige accounttoegang')
        if st.form_submit_button('Account deactiveren' if target['actief'] else 'Account heractiveren'):
            if not confirmed:
                st.error('Bevestig eerst de wijziging.')
            elif run(lambda: api.set_account_active(token,uid,not target['actief'],reason),'Accountstatus gewijzigd.'):
                st.rerun()
    st.caption('De platformeigenaar en je eigen account kunnen niet worden gedeactiveerd. Een organisatie-eigenaar vereist eerst eigendomsoverdracht; blokkeer zo nodig de organisatie. Alleen de platformeigenaar mag andere platformbeheerders deactiveren.')
