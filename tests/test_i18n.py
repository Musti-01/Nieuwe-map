from clock_helpers import planned_clock_in
import ast
import string
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
import streamlit as st
from workforce.i18n import LANGUAGES, catalogs, tr, set_language, translated_table
from workforce.service import Denied

@pytest.fixture(autouse=True)
def reset_language_context():
    set_language('nl')
    yield
    set_language('nl')


def test_catalog_has_complete_languages_and_matching_placeholders():
    parser=string.Formatter()
    for source,translations in catalogs().items():
        assert set(translations)=={'fr','en','de','es'},source
        expected={field for _,field,_,_ in parser.parse(source) if field is not None}
        for language,value in translations.items():
            assert value.strip(),(source,language)
            assert {field for _,field,_,_ in parser.parse(value) if field is not None}==expected,(source,language)


def test_all_static_interface_strings_are_catalogued():
    for path in [Path('app.py'),*Path('workforce').glob('ui_*.py')]:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='tr' and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
                assert node.args[0].value in catalogs(),(path,node.args[0].value)


def test_server_validation_messages_have_translations():
    for node in ast.walk(ast.parse(Path('workforce/service.py').read_text())):
        if isinstance(node,ast.Raise) and isinstance(node.exc,ast.Call) and node.exc.args:
            arg=node.exc.args[0]
            if isinstance(arg,ast.Constant) and isinstance(arg.value,str):
                assert arg.value in catalogs(),arg.value


def test_dynamic_errors_and_personal_data_are_preserved():
    set_language('fr')
    assert tr('Naam: vul 1 tot 120 tekens in.')=='Nom : saisissez entre 1 et 120 caractères.'
    rows=translated_table([{'Medewerker':'Overzicht','Status':'Wacht op controle','Opmerking':'Inloggen'}])
    assert rows==[{'Employé':'Overzicht','Statut':'En attente de contrôle','Remarque':'Inloggen'}]
    assert tr('Adres: {v0}',v0='Inloggen 12')=='Adresse : Inloggen 12'
    assert tr('onbekende technische tekst')=='onbekende technische tekst'


@pytest.mark.parametrize('language',['nl','fr','en','de','es'])
def test_login_registration_and_error_in_every_language(engine,monkeypatch,language):
    monkeypatch.setenv('DATABASE_URL',engine.url.render_as_string(hide_password=False))
    monkeypatch.delenv('AUTO_MIGRATE',raising=False)
    st.cache_resource.clear()
    app=AppTest.from_file('app.py',default_timeout=10).run()
    app.selectbox(key='language').set_value(language).run()
    set_language(language)
    assert [tab.label for tab in app.tabs]==[tr('Inloggen'),tr('Registreren')]
    assert any(x.label==tr('Wachtwoord') for x in app.text_input)
    assert not app.exception
    # Invalid input returns a localized validation message, rather than leaking Dutch.
    next(b for b in app.button if b.label==tr('Inloggen')).click().run()
    assert any(e.value==tr('Vul een geldig e-mailadres in.') for e in app.error)


def test_language_preference_is_per_account_and_authorized(api,team):
    api.set_language(team['wt'],'es')
    assert api.identity(team['wt'])['language']=='es'
    assert api.identity(team['ot'])['language']=='nl'
    with pytest.raises(ValueError):
        api.set_language(team['wt'],'xx')
    with pytest.raises(Denied):
        api.set_language('invalid-session','en')
    api.logout(team['wt'])
    fresh=api.login('worker@example.test','Correct-test-password!')
    assert api.identity(fresh)['language']=='es'


@pytest.mark.parametrize('language',['fr','en','de','es'])
def test_employee_shift_screen_and_preference_restore(api,team,engine,monkeypatch,language):
    monkeypatch.setenv('DATABASE_URL',engine.url.render_as_string(hide_password=False))
    monkeypatch.delenv('AUTO_MIGRATE',raising=False)
    planned_clock_in(api, team['wt'],team['branch']);api.clock_out(team['wt'],team['branch'])
    api.set_language(team['wt'],language)
    st.cache_resource.clear()
    app=AppTest.from_file('app.py',default_timeout=10)
    app.session_state['token']=team['wt']
    app.run();set_language(language)
    assert not app.exception
    assert app.selectbox(key='language').value==language
    assert app.tabs[1].label==tr('Mijn shiften')
    assert app.dataframe[0].value.iloc[0][tr('Status')]==tr('Wacht op controle')
    app.selectbox(key='language').set_value('nl').run()
    assert api.identity(team['wt'])['language']=='nl'


def test_account_creation_keeps_chosen_language(api):
    api.register('spanish@example.test','Inloggen','Strong-password-123',language='es')
    token=api.login('spanish@example.test','Strong-password-123')
    assert api.identity(token)['language']=='es'
    assert api.identity(token)['name']=='Inloggen'


@pytest.mark.parametrize('language',['fr','en','de','es'])
def test_platform_approval_works_in_translated_interface(api,team,engine,monkeypatch,language):
    branch=api.add_branch(team['ot'],api.organizations(team['ot'])[0]['id'],'Inloggen','Voorbeeldadres 1')
    api.set_language(team['pt'],language)
    monkeypatch.setenv('DATABASE_URL',engine.url.render_as_string(hide_password=False))
    monkeypatch.delenv('AUTO_MIGRATE',raising=False)
    st.cache_resource.clear()
    app=AppTest.from_file('app.py',default_timeout=10)
    app.session_state['token']=team['pt']
    app.run();set_language(language)
    app.radio(key='platform_page').set_value('Aanvragen').run()
    next(s for s in app.selectbox if s.label==tr('Filter op status')).set_value('In afwachting').run()
    assert not app.exception
    next(b for b in app.button if b.label==tr('Besluit bevestigen')).click().run()
    assert not app.exception
    assert next(b for b in api.branches(team['ot']) if b['id']==branch)['status']=='approved'
    assert next(b for b in api.branches(team['ot']) if b['id']==branch)['name']=='Inloggen'


def test_logout_keeps_language_but_clears_authentication(api,team,engine,monkeypatch):
    api.set_language(team['wt'],'fr')
    monkeypatch.setenv('DATABASE_URL',engine.url.render_as_string(hide_password=False))
    monkeypatch.delenv('AUTO_MIGRATE',raising=False)
    st.cache_resource.clear()
    app=AppTest.from_file('app.py',default_timeout=10)
    app.session_state['token']=team['wt']
    app.run()
    set_language('fr')
    next(b for b in app.button if b.label=='Se déconnecter').click().run()
    assert not app.exception
    assert app.selectbox(key='language').value=='fr'
    assert [tab.label for tab in app.tabs]==['Se connecter','Créer un compte']
    with pytest.raises(KeyError):
        app.session_state['token']


@pytest.mark.parametrize('language',['fr','en','de','es'])
def test_manager_home_and_direct_invitation_in_every_language(api,team,engine,monkeypatch,language):
    api.set_language(team['ot'],language)
    monkeypatch.setenv('DATABASE_URL',engine.url.render_as_string(hide_password=False))
    monkeypatch.delenv('AUTO_MIGRATE',raising=False)
    st.cache_resource.clear()
    app=AppTest.from_file('app.py',default_timeout=10)
    app.session_state['token']=team['ot']
    app.run();set_language(language)
    assert not app.exception
    assert any(h.value==tr('Jouw vestiging beheren') for h in app.subheader)
    assert not any(b.label==tr('Inklokken') for b in app.button)
    assert app.button(key='manager_open_Medewerkers toevoegen').label==tr('Medewerkers toevoegen')
    app.button(key='manager_open_Medewerkers toevoegen').click().run()
    assert not app.exception
    assert any(b.label==tr('Uitnodiging maken') for b in app.button)
