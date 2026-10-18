from clock_helpers import planned_clock_in
import pytest
from sqlalchemy import select
from workforce.models import Branch, WorkEntry, Audit
from workforce.service import Denied


def test_remove_branch_revokes_access_and_preserves_history(api, team):
    planned_clock_in(api, team['wt'], team['branch'])
    assert api.archive_branch(team['pt'], team['branch'])
    assert api.branches(team['wt']) == []
    assert api.branches(team['ot']) == []
    assert api.branches(team['xt'])[0]['id'] == team['other_branch']
    assert not any(r['kind']=='branch' and r['id']==team['branch'] for r in api.applications(team['pt']))
    with api.sessions() as s:
        branch=s.get(Branch,team['branch'])
        entry=s.scalar(select(WorkEntry).where(WorkEntry.branch_id==branch.id))
        assert branch.archived_at and branch.archived_by
        assert entry.ended_at == branch.archived_at
        assert entry.review_status=='pending'
        assert s.scalar(select(Audit).where(Audit.action=='branch.archived'))
    with pytest.raises(Denied):
        api.clock_in(team['wt'],team['branch'])
    with pytest.raises(Denied):
        api.decide(team['pt'],'branch',team['branch'],'block','test')
    api.archive_branch(team['pt'],team['branch'],restore=True)
    assert api.branches(team['wt'])[0]['id']==team['branch']
    planned_clock_in(api, team['wt'],team['branch'])


@pytest.mark.parametrize('token_key',['ot','wt','xt'])
def test_only_platform_can_remove_or_restore(api,team,token_key):
    for restore in (False,True):
        with pytest.raises(Denied):
            api.archive_branch(team[token_key],team['branch'],restore=restore)
    with pytest.raises(Denied):
        api.platform_branches(team[token_key])


def test_removed_branch_filter_and_repeat_removal(api,team):
    api.archive_branch(team['pt'],team['branch'])
    api.archive_branch(team['pt'],team['branch'])
    assert [b['id'] for b in api.platform_branches(team['pt'],archived=True)]==[team['branch']]
    assert [b['id'] for b in api.platform_branches(team['pt'])]==[team['other_branch']]


def test_platform_remove_requires_single_confirmation(api,team,engine,monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('DATABASE_URL',engine.url.render_as_string(hide_password=False))
    monkeypatch.delenv('AUTO_MIGRATE',raising=False)
    st.cache_resource.clear()
    app=AppTest.from_file('app.py',default_timeout=10)
    app.session_state['token']=team['pt']
    app.session_state['platform_page']='Vestigingen beheren'
    app.run()
    assert not app.exception
    app.button(key=f"remove_branch_{team['branch']}").click().run()
    assert api.branches(team['wt'])
    app.button(key=f"confirm_branch_{team['branch']}").click().run()
    assert not app.exception
    assert api.branches(team['wt'])==[]


def test_last_branch_removal_hides_parent_request_but_restoration_recovers_it(api,team):
    org=api.organizations(team['ot'])[0]['id']
    decisions=api.decisions(team['pt'])
    api.archive_branch(team['pt'],team['branch'])
    assert not any(r['organization_id']==org for r in api.applications(team['pt']))
    assert any(r['id']==org for r in api.organizations(team['ot']))
    assert api.decisions(team['pt'])==decisions
    assert any(r['id']==team['branch'] for r in api.platform_branches(team['pt'],archived=True))
    api.archive_branch(team['pt'],team['branch'],restore=True)
    rows=[r for r in api.applications(team['pt']) if r['organization_id']==org]
    assert {(r['kind'],r['id']) for r in rows}=={('organization',org),('branch',team['branch'])}


def test_remaining_branch_keeps_organization_visible_and_new_request_reappears(api,team):
    org=api.organizations(team['ot'])[0]['id']
    extra=api.add_branch(team['ot'],org,'Extra','Voorbeeldstraat 2')
    api.archive_branch(team['pt'],team['branch'])
    rows=[r for r in api.applications(team['pt']) if r['organization_id']==org]
    assert {(r['kind'],r['id']) for r in rows}=={('organization',org),('branch',extra)}
    assert next(r for r in rows if r['kind']=='branch')['status']=='pending'
    api.archive_branch(team['pt'],extra)
    assert not any(r['organization_id']==org for r in api.applications(team['pt']))
    fresh=api.add_branch(team['ot'],org,'Nieuwe aanvraag','Voorbeeldstraat 3')
    rows=[r for r in api.applications(team['pt']) if r['organization_id']==org]
    assert {(r['kind'],r['id']) for r in rows}=={('organization',org),('branch',fresh)}


def test_deleted_organization_is_absent_from_application_table_and_selector(api,team,engine,monkeypatch):
    from test_ui import app_for
    api.archive_branch(team['pt'],team['branch'])
    app=app_for(team['pt'],engine,monkeypatch)
    app.radio(key='platform_page').set_value('Aanvragen').run()
    assert not app.exception
    assert 'Org A' not in list(app.dataframe[0].value['Bedrijf'])
    selector=next(s for s in app.selectbox if s.label=='Aanvraag beoordelen')
    assert all('Org A' not in option for option in selector.options)
    assert 'Org B' in list(app.dataframe[0].value['Bedrijf'])
