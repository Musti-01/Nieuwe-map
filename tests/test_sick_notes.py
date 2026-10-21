from io import BytesIO
import pytest
from PIL import Image
from workforce.service import Denied
from workforce.sick_notes import MAX_SIZE, validate_note


def attachment(format='PDF'):
    output = BytesIO()
    Image.new('RGB', (8, 8), 'white').save(output, format=format)
    return output.getvalue()


@pytest.mark.parametrize('suffix,format,mime', [('pdf','PDF','application/pdf'), ('png','PNG','image/png'), ('jpg','JPEG','image/jpeg')])
def test_upload_list_and_download(api, team, suffix, format, mime):
    content = attachment(format)
    note_id = api.upload_sick_note(team['wt'], team['branch'], f'../../brief.{suffix}', content)
    notes = api.sick_notes(team['wt'], team['branch'])
    assert len(notes) == 1 and notes[0]['id'] == note_id
    assert notes[0]['filename'] == f'brief.{suffix}'
    assert 'content' not in notes[0]
    for token in (team['pt'],):
        assert api.download_sick_note(token, team['branch'], note_id) == {
            'filename': f'brief.{suffix}', 'media_type': mime, 'content': content}
    assert api.sick_notes(team['ot'], team['branch']) == []
    with pytest.raises(Denied):
        api.sick_notes(team['ot'], team['branch'], team=True)
    assert api.sick_notes(team['pt'], team['branch'], team=True)[0]['id'] == note_id
    for token in (team['wt'], team['ot']):
        with pytest.raises(Denied):
            api.download_sick_note(token, team['branch'], note_id)
    events = api.audit(team['ot'], team['branch'])
    assert any(e['actie'] == 'sick_note.uploaded' for e in events)
    assert any(e['actie'] == 'sick_note.downloaded' for e in events)
    assert all('brief.' not in e['detail'] for e in events)


def test_isolation_and_live_access(api, team):
    note_id = api.upload_sick_note(team['wt'], team['branch'], 'brief.pdf', attachment())
    api.register('colleague@example.test', 'Colleague', 'Correct-test-password!')
    colleague = api.login('colleague@example.test', 'Correct-test-password!')
    uid = api.identity(colleague)['id']
    api.set_role(team['ot'], team['branch'], uid, 'employee')
    assert api.sick_notes(colleague, team['branch']) == []
    with pytest.raises(Denied):
        api.sick_notes(colleague, team['branch'], team=True)
    with pytest.raises(Denied):
        api.download_sick_note(colleague, team['branch'], note_id)
    with pytest.raises(Denied):
        api.download_sick_note(team['xt'], team['other_branch'], note_id)
    with pytest.raises(Denied):
        api.upload_sick_note(team['xt'], team['branch'], 'brief.pdf', attachment())
    # Branch admin rights never grant access to medical files.
    api.set_role(team['ot'], team['branch'], uid, 'admin')
    with pytest.raises(Denied):
        api.download_sick_note(colleague, team['branch'], note_id)
    api.delegate_platform(team['pt'], 'colleague@example.test', True)
    assert api.download_sick_note(colleague, team['branch'], note_id)['content']
    api.delegate_platform(team['pt'], 'colleague@example.test', False)
    api.set_role(team['ot'], team['branch'], uid, 'employee')
    with pytest.raises(Denied):
        api.download_sick_note(colleague, team['branch'], note_id)
    api.set_role(team['ot'], team['branch'], team['worker'], None)
    with pytest.raises(Denied):
        api.download_sick_note(team['wt'], team['branch'], note_id)
    api.logout(team['ot'])
    with pytest.raises(Denied):
        api.download_sick_note(team['ot'], team['branch'], note_id)


@pytest.mark.parametrize('name,data', [
    ('brief.pdf', b''), ('brief.pdf', b'x' * (MAX_SIZE + 1)),
    ('brief.pdf', b'not a pdf'), ('brief.html', b'<html>'),
    ('brief.png', b'%PDF-1.4\n%%EOF'), ('brief.jpg', b'broken image'),
    ('bad\nname.pdf', b'%PDF-1.4\n%%EOF'),
])
def test_invalid_files(name, data):
    with pytest.raises(ValueError):
        validate_note(name, data)


def test_blocked_branch_and_unassigned_owner(api, team):
    with pytest.raises(Denied):
        api.upload_sick_note(team['pt'], team['branch'], 'brief.pdf', attachment())
    note_id = api.upload_sick_note(team['wt'], team['branch'], 'brief.pdf', attachment())
    api.decide(team['pt'], 'branch', team['branch'], 'block', 'Closed')
    with pytest.raises(Denied):
        api.download_sick_note(team['ot'], team['branch'], note_id)
    with pytest.raises(Denied):
        api.upload_sick_note(team['wt'], team['branch'], 'brief.pdf', attachment())


def test_manager_and_employee_ui(api, team, engine, monkeypatch):
    from test_ui import app_for
    note_id = api.upload_sick_note(team['wt'], team['branch'], 'brief.pdf', attachment())
    app = app_for(team['ot'], engine, monkeypatch)
    app.radio(key=f"branch_page_{team['branch']}").set_value('Ziektebriefjes').run()
    assert not app.exception
    assert not any(str(b.key).startswith('sick_note_fetch_') for b in app.button)
    app = app_for(team['pt'], engine, monkeypatch)
    next(r for r in app.radio if r.label == 'Werkruimte').set_value('Vestigingen').run()
    app.radio(key=f"branch_page_{team['branch']}").set_value('Ziektebriefjes').run()
    app.button(key=f"sick_note_fetch_{team['branch']}_{note_id}").click().run()
    assert not app.exception
    assert len(app.get('download_button')) == 1
    employee = app_for(team['wt'], engine, monkeypatch)
    assert not employee.exception
    assert employee.tabs[4].label == 'Ziektebriefjes'
    next(b for b in employee.button if b.label == 'Ziektebrief indienen').click().run()
    assert employee.error and not employee.exception
