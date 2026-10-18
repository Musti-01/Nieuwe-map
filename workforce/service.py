"""Every public operation authenticates and authorizes in the same transaction."""
import os
from urllib.parse import urlsplit, urlencode
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import select, or_, text, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert
from workforce.models import User, Organization, Branch, Membership, WorkEntry, AuthSession, LoginLimit, Audit, ApprovalDecision, Notification, ShiftReview, AccountToken, ShiftPlan

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))

def now():
    return datetime.now(timezone.utc)

class Denied(ValueError):
    pass

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def clean(value, label, maximum=120):
    value = value.strip()
    if not value or len(value) > maximum:
        raise ValueError(f"{label}: vul 1 tot {maximum} tekens in.")
    return value

def email_address(value):
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Vul een geldig e-mailadres in.")
    return value

class Service:
    def __init__(self, session_factory):
        self.sessions = session_factory

    def register(self, email, name, password, organization=None, chain=None, branch=None, address=None, phone=None, language="nl"):
        if language not in ("nl","fr","en","de","es"):
            raise ValueError("Ongeldige taalkeuze.")
        email = email_address(email)
        name = clean(name, "Naam")
        if len(password) < 12 or len(password) > 128:
            raise ValueError("Gebruik een wachtwoord van 12 tot 128 tekens.")
        if organization is not None:
            organization, chain, branch = (clean(v or "", l) for v, l in [(organization, "Organisatie"), (chain, "Keten"), (branch, "Vestiging")])
        if organization is not None:
            address = clean(address or "", "Adres", 255)
            phone = clean(phone or "", "Telefoon", 40)
        try:
            with self.sessions.begin() as s:
                u = User(email=email, name=name, password_hash=hasher.hash(password), platform_admin=False, language=language)
                s.add(u)
                s.flush()
                if organization is not None:
                    org = Organization(name=organization, chain=chain, owner_id=u.id, address=address, contact_phone=phone, status="pending")
                    s.add(org)
                    s.flush()
                    b = Branch(name=branch, organization_id=org.id, address=address, status="pending")
                    s.add(b)
                    s.flush()
                    s.add(Membership(branch_id=b.id, user_id=u.id, role="admin"))
                return u.id
        except IntegrityError as exc:
            raise ValueError("Registratie niet mogelijk met dit e-mailadres.") from exc

    def login(self, email, password):
        email = email_address(email)
        if len(password) > 128:
            raise Denied("Ongeldige inloggegevens.")
        success = False
        token = None
        with self.sessions.begin() as s:
            key = digest(email)
            s.execute(insert(LoginLimit).values(key=key, failures=0, window_start=now()).on_conflict_do_nothing())
            limit = s.scalar(select(LoginLimit).where(LoginLimit.key == key).with_for_update())
            if now() - limit.window_start >= timedelta(minutes=15):
                limit.failures, limit.window_start = 0, now()
            if limit.failures >= 5:
                raise Denied("Te veel pogingen. Probeer over 15 minuten opnieuw.")
            u = s.scalar(select(User).where(User.email == email))
            try:
                success = hasher.verify(u.password_hash if u else DUMMY_HASH, password) and u is not None and u.is_active
            except (VerificationError, InvalidHashError):
                success = False
            if success:
                if hasher.check_needs_rehash(u.password_hash):
                    u.password_hash = hasher.hash(password)
                limit.failures = 0
                token = secrets.token_urlsafe(32)
                s.add(AuthSession(token_hash=digest(token), user_id=u.id, expires_at=now() + timedelta(hours=8)))
            else:
                limit.failures += 1
        if not success:
            raise Denied("Ongeldige inloggegevens.")
        return token

    def _actor(self, s, token):
        if not isinstance(token, str) or not token:
            raise Denied("Log opnieuw in.")
        u = s.scalar(select(User).join(AuthSession).where(AuthSession.token_hash == digest(token), AuthSession.expires_at > now(), User.is_active.is_(True)))
        if not u:
            raise Denied("Sessie verlopen. Log opnieuw in.")
        return u

    def identity(self, token):
        with self.sessions.begin() as s:
            u = self._actor(s, token)
            return {"id": u.id, "name": u.name, "email": u.email, "platform_admin": u.platform_admin, "platform_owner": u.platform_owner, "language": u.language}

    def logout(self, token):
        with self.sessions.begin() as s:
            s.execute(delete(AuthSession).where(AuthSession.token_hash == digest(token)))

    def _access(self, s, u, branch_id, admin=False, owner=False, lock=False):
        b = s.get(Branch, branch_id)
        if not b:
            raise Denied("Geen toegang tot deze vestiging.")
        if lock:
            org = s.scalar(select(Organization).where(Organization.id == b.organization_id).with_for_update().execution_options(populate_existing=True))
            b = s.scalar(select(Branch).where(Branch.id == b.id).with_for_update().execution_options(populate_existing=True))
        else:
            org = s.get(Organization, b.organization_id)
        u = s.get(User, u.id, populate_existing=True)
        if not u or not u.is_active:
            raise Denied("Dit account is gedeactiveerd.")
        if b.archived_at is not None or org.status != "approved" or b.status != "approved":
            raise Denied("Organisatie en vestiging moeten actief en goedgekeurd zijn.")
        if u.platform_admin or org.owner_id == u.id:
            return b
        m = s.get(Membership, (b.id, u.id), populate_existing=True)
        if owner or not m or m.role == "revoked" or (admin and m.role != "admin"):
            raise Denied("Geen toegang tot deze vestiging.")
        return b

    def organizations(self, token):
        with self.sessions.begin() as s:
            u = self._actor(s, token)
            q = select(Organization)
            if not u.platform_admin:
                q = q.where(Organization.owner_id == u.id)
            return [{"id": o.id, "name": o.name, "chain": o.chain, "status": o.status} for o in s.scalars(q.order_by(Organization.id))]

    def branches(self, token):
        with self.sessions.begin() as s:
            u = self._actor(s, token)
            q = select(Branch, Organization).join(Organization).where(Branch.archived_at.is_(None))
            if not u.platform_admin:
                q = q.where(or_(Organization.owner_id == u.id, Branch.id.in_(select(Membership.branch_id).where(Membership.user_id == u.id, Membership.role != "revoked"))))
            result = []
            for b, o in s.execute(q.order_by(Organization.name, Branch.name)):
                m = s.get(Membership, (b.id, u.id), populate_existing=True)
                result.append({"id": b.id, "name": b.name, "organization": o.name, "organization_id": o.id, "status": b.status, "organization_status": o.status, "owner": u.platform_admin or o.owner_id == u.id, "admin": u.platform_admin or o.owner_id == u.id or (m is not None and m.role == "admin"), "member": m is not None and m.role != "revoked"})
            return result

    def add_branch(self, token, organization_id, name, address):
        address = clean(address, "Adres", 255)
        name = clean(name, "Vestiging")
        with self.sessions.begin() as s:
            u = self._actor(s, token)
            org = s.get(Organization, organization_id)
            if not org or (org.owner_id != u.id and not u.platform_admin):
                raise Denied("Alleen de organisatie-eigenaar kan vestigingen toevoegen.")
            b = Branch(organization_id=org.id, name=name, address=address, status="pending")
            s.add(b)
            s.flush()
            s.add(Membership(branch_id=b.id, user_id=u.id, role="admin"))
            self._audit(s, u, b.id, "branch.created", name)
            return b.id

    def lookup_user(self, token, branch_id, email):
        email = email_address(email)
        with self.sessions.begin() as s:
            u = self._actor(s, token)
            self._access(s, u, branch_id, admin=True)
            target = s.scalar(select(User).where(User.email == email))
            return None if not target else {"id": target.id, "name": target.name, "email": target.email}

    def set_role(self, token, branch_id, target_id, role):
        if role not in ("employee", "admin", None):
            raise ValueError("Ongeldige rol.")
        with self.sessions.begin() as s:
            u = self._actor(s, token)
            b = self._access(s, u, branch_id, admin=True, lock=True)
            org = s.get(Organization, b.organization_id)
            target = s.get(User, target_id)
            if not target or not target.is_active:
                raise ValueError("Actieve gebruiker niet gevonden.")
            m = s.get(Membership, (b.id, target.id), populate_existing=True)
            is_owner = u.platform_admin or org.owner_id == u.id
            if not is_owner and (role == "admin" or (m and m.role == "admin") or target.id == org.owner_id or target.platform_admin):
                raise Denied("Alleen de eigenaar kan beheerdersrechten wijzigen.")
            if target.id == org.owner_id and role != "admin":
                raise Denied("De eigenaar behoudt zijn beheerdersrechten.")
            # Revocation keeps historical membership for FK integrity and sets no access.
            if role is None:
                if s.scalar(select(WorkEntry.id).where(WorkEntry.user_id == target.id, WorkEntry.branch_id == b.id, WorkEntry.ended_at.is_(None))):
                    raise ValueError("Laat deze medewerker eerst uitklokken.")
                if m:
                    m.role = "revoked"
            elif m:
                m.role = role
            else:
                s.add(Membership(branch_id=b.id, user_id=target.id, role=role))
            self._audit(s, u, b.id, "membership.changed", f"user={target.id}; role={role or 'revoked'}")

    def members(self, token, branch_id):
        with self.sessions.begin() as s:
            u = self._actor(s, token)
            self._access(s, u, branch_id, admin=True)
            return [{"id": member.id, "name": member.name, "email": member.email, "role": m.role, "active": member.is_active} for member, m in s.execute(select(User, Membership).join(Membership).where(Membership.branch_id == branch_id).order_by(User.name))]

    def clock_in(self, token, branch_id, plan_id=None):
        try:
            with self.sessions.begin() as s:
                u = self._actor(s, token)
                self._access(s, u, branch_id, lock=True)
                s.execute(text("SELECT pg_advisory_xact_lock(793125043, :uid)"), {"uid": u.id})
                m = s.get(Membership, (branch_id, u.id))
                if not m or m.role == "revoked":
                    raise Denied("Je bent geen medewerker van deze vestiging.")
                if plan_id is not None:
                    plan = s.get(ShiftPlan, plan_id)
                    if not plan or plan.branch_id != branch_id or plan.user_id != u.id or plan.status != 'scheduled':
                        raise Denied("Geen toegang tot deze geplande shift.")
                    if s.scalar(select(WorkEntry.id).where(WorkEntry.plan_id == plan_id)):
                        raise ValueError("Deze geplande shift heeft al een tijdregistratie.")
                e = WorkEntry(branch_id=branch_id, user_id=u.id, started_at=now(), plan_id=plan_id)
                s.add(e)
                s.flush()
                self._audit(s, u, branch_id, "clock.in", f"entry={e.id}")
                return e.id
        except IntegrityError as exc:
            raise ValueError("Je hebt al een actieve inkloksessie.") from exc

    def clock_out(self, token, branch_id):
        with self.sessions.begin() as s:
            u = self._actor(s, token)
            self._access(s, u, branch_id, lock=True)
            s.execute(text("SELECT pg_advisory_xact_lock(793125043, :uid)"), {"uid": u.id})
            e = s.scalar(select(WorkEntry).where(WorkEntry.user_id == u.id, WorkEntry.branch_id == branch_id, WorkEntry.ended_at.is_(None)).with_for_update())
            if not e:
                raise ValueError("Geen actieve sessie in deze vestiging.")
            e.ended_at = now()
            e.version += 1
            self._audit(s, u, branch_id, "clock.out", f"entry={e.id}")
            return e.id

    def entries(self, token, branch_id, team=False):
        with self.sessions.begin() as s:
            u = self._actor(s, token)
            self._access(s, u, branch_id, admin=team)
            q = select(WorkEntry, User.name).join(User, User.id == WorkEntry.user_id).where(WorkEntry.branch_id == branch_id)
            if not team:
                q = q.where(WorkEntry.user_id == u.id)
            return [{"id": e.id, "user_id": e.user_id, "name": name, "start": e.started_at, "end": e.ended_at, "review_status": e.review_status, "version": e.version, "reviewed_by": e.reviewed_by, "reviewed_at": e.reviewed_at, "plan_id": e.plan_id} for e, name in s.execute(q.order_by(WorkEntry.started_at.desc()))]

    def audit(self, token, branch_id):
        with self.sessions.begin() as s:
            u = self._actor(s, token)
            self._access(s, u, branch_id, admin=True)
            result = []
            for a, actor_name in s.execute(select(Audit, User.name).join(User, User.id == Audit.actor_id).where(Audit.branch_id == branch_id).order_by(Audit.id.desc()).limit(100)):
                row = {"tijd": a.created_at, "actor": a.actor_id, "actor_name": actor_name,
                       "actie": a.action, "detail": a.detail, "subject": "", "reason": ""}
                fields = dict(re.findall(r"(?:^|; )([a-z]+)=([^;]*)", a.detail))
                entry = None
                if fields.get('entry', '').isdigit():
                    entry = s.scalar(select(WorkEntry).where(WorkEntry.id == int(fields['entry']), WorkEntry.branch_id == branch_id))
                plan = None
                if fields.get('plan', '').isdigit():
                    plan = s.scalar(select(ShiftPlan).where(ShiftPlan.id == int(fields['plan']), ShiftPlan.branch_id == branch_id))
                target_id = entry.user_id if entry else plan.user_id if plan else None
                if a.action == 'membership.changed' and fields.get('user', '').isdigit():
                    target_id = int(fields['user'])
                    row['role'] = fields.get('role')
                if target_id:
                    person = s.get(User, target_id)
                    row['subject'] = person.name if person else ''
                elif a.action == 'account.invited':
                    row['subject'] = fields.get('email', '')
                elif a.action.startswith(('branch.', 'approval.')):
                    row['subject'] = s.get(Branch, branch_id).name
                elif a.action == 'invitation.accepted':
                    row['subject'] = actor_name
                if entry and fields.get('review', '').isdigit():
                    review = s.scalar(select(ShiftReview).where(ShiftReview.id == int(fields['review']), ShiftReview.entry_id == entry.id))
                    if review:
                        row.update(reason=review.reason, old_start=review.old_start, old_end=review.old_end,
                                   new_start=review.new_start, new_end=review.new_end)
                elif a.action == 'plan.cancelled':
                    row['reason'] = a.detail.partition('; reason=')[2]
                if a.action.startswith('approval.'):
                    transition = re.search(r'; (pending|approved|blocked|rejected)->(pending|approved|blocked|rejected);', a.detail)
                    if transition:
                        row['previous_status'], row['status'] = transition.groups()
                result.append(row)
            return result

    def _audit(self, s, u, branch_id, action, detail):
        s.add(Audit(actor_id=u.id, branch_id=branch_id, action=action, detail=detail, created_at=now()))

    def bootstrap(self, email):
        """Local operator only: promotes one registered account, exactly once."""
        email = email_address(email)
        with self.sessions.begin() as s:
            s.execute(text("SELECT pg_advisory_xact_lock(793125041)"))
            if s.scalar(select(User.id).where(User.platform_admin.is_(True))):
                raise ValueError("Platformbeheerder bestaat al; bootstrap is gesloten.")
            u = s.scalar(select(User).where(User.email == email))
            if not u:
                raise ValueError("Registreer eerst jouw persoonlijke account.")
            u.platform_admin = True
            u.platform_owner = True
            self._audit(s, u, None, "platform.bootstrap", f"user={u.id}")

    def _platform(self, s, token, owner=False):
        u = self._actor(s, token)
        u = s.scalar(select(User).where(User.id == u.id).with_for_update().execution_options(populate_existing=True))
        if not u or not u.is_active or not u.platform_admin or (owner and not u.platform_owner):
            raise Denied("Alleen bevoegde platformbeheerders hebben toegang.")
        return u

    def applications(self, token):
        with self.sessions.begin() as s:
            self._platform(s, token)
            result = []
            for org, responsible in s.execute(select(Organization, User).join(User, User.id == Organization.owner_id).order_by(Organization.id)):
                for entity in [org, *s.scalars(select(Branch).where(Branch.organization_id == org.id, Branch.archived_at.is_(None)).order_by(Branch.id))]:
                    result.append({"kind": "organization" if entity is org else "branch", "id": entity.id, "organization_id": org.id, "bedrijf": org.name, "vestiging": "—" if entity is org else entity.name, "adres": entity.address, "verantwoordelijke": responsible.name, "email": responsible.email, "telefoon": org.contact_phone, "status": entity.status, "aangevraagd": entity.submitted_at, "beoordelaar": entity.reviewed_by, "beoordeeld": entity.reviewed_at})
            return result

    def decide(self, token, kind, entity_id, action, reason=""):
        model = {"organization": Organization, "branch": Branch}.get(kind)
        transitions = {"approve": ("pending", "approved"), "reject": ("pending", "rejected"), "block": ("approved", "blocked"), "reactivate": ("blocked", "approved")}
        if not model or action not in transitions:
            raise ValueError("Ongeldig besluit.")
        reason = reason.strip()
        if len(reason) > 500 or (action in ("reject", "block") and not reason):
            raise ValueError("Geef een reden van maximaal 500 tekens bij weigeren of blokkeren.")
        with self.sessions.begin() as s:
            u = self._platform(s, token)
            # Always lock organization before branch: same ordering for operational writes.
            if kind == "branch":
                initial = s.get(Branch, entity_id)
                if not initial:
                    raise ValueError("Aanvraag niet gevonden.")
                org_id = initial.organization_id
            else:
                org_id = entity_id
            org = s.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            if not org:
                raise ValueError("Aanvraag niet gevonden.")
            entity = org if kind == "organization" else s.scalar(select(Branch).where(Branch.id == entity_id).with_for_update().execution_options(populate_existing=True))
            if kind == "branch" and entity.archived_at is not None:
                raise Denied("Deze vestiging is verwijderd. Herstel deze eerst.")
            old, new = transitions[action]
            if entity.status != old:
                raise ValueError("Besluit past niet bij de huidige status; vernieuw het overzicht.")
            if kind == "branch" and new == "approved" and org.status != "approved":
                raise ValueError("Keur eerst de organisatie goed of activeer deze opnieuw.")
            entity.status, entity.reviewed_by, entity.reviewed_at = new, u.id, now()
            d = ApprovalDecision(organization_id=org.id, branch_id=entity.id if kind == "branch" else None, reviewer_id=u.id, previous_status=old, status=new, reason=reason, occurred_at=entity.reviewed_at)
            s.add(d)
            s.flush()
            if action == "block":
                branches = select(Branch.id).where(Branch.organization_id == org.id) if kind == "organization" else [entity.id]
                active = list(s.scalars(select(WorkEntry).where(WorkEntry.branch_id.in_(branches), WorkEntry.ended_at.is_(None)).with_for_update()))
                for entry in active:
                    entry.ended_at = entity.reviewed_at
                    entry.version += 1
                    self._audit(s, u, entry.branch_id, "clock.closed_by_block", f"entry={entry.id}; decision={d.id}")
            self._audit(s, u, d.branch_id, "approval." + action, f"{kind}={entity.id}; {old}->{new}; decision={d.id}")
            owner_user = s.get(User, org.owner_id)
            title = {"approved": "Goedgekeurd", "rejected": "Geweigerd", "blocked": "Geblokkeerd"}[new]
            s.add(Notification(decision_id=d.id, recipient=owner_user.email, subject=f"ShiftFlow: {title}", body=f"Beste {owner_user.name},\n\nDe aanvraag voor {entity.name} ({kind}) heeft status: {title}.\nReden: {reason or 'Geen aanvullende toelichting.'}\n\nOrganisatie en vestiging moeten beide goedgekeurd zijn om operationele functies te gebruiken."))
            return d.id

    def platform_branches(self, token, archived=False):
        with self.sessions.begin() as s:
            self._platform(s, token)
            q = select(Branch, Organization).join(Organization)
            q = q.where(Branch.archived_at.is_not(None) if archived else Branch.archived_at.is_(None))
            return [{"id": b.id, "name": b.name, "organization": o.name,
                     "address": b.address, "status": b.status, "archived_at": b.archived_at}
                    for b, o in s.execute(q.order_by(Organization.name, Branch.name))]

    def archive_branch(self, token, branch_id, restore=False):
        with self.sessions.begin() as s:
            u = self._platform(s, token)
            initial = s.get(Branch, branch_id)
            if not initial:
                raise Denied("Geen toegang tot deze vestiging.")
            s.scalar(select(Organization).where(Organization.id == initial.organization_id).with_for_update())
            b = s.scalar(select(Branch).where(Branch.id == branch_id).with_for_update().execution_options(populate_existing=True))
            if restore:
                b.archived_at = b.archived_by = None
            elif b.archived_at is None:
                b.archived_at, b.archived_by = now(), u.id
                entries = s.scalars(select(WorkEntry).where(WorkEntry.branch_id == b.id, WorkEntry.ended_at.is_(None)).with_for_update())
                for entry in entries:
                    entry.ended_at = b.archived_at
                    entry.version += 1
                    self._audit(s, u, b.id, "clock.closed_by_archive", f"entry={entry.id}")
            else:
                return True
            self._audit(s, u, b.id, "branch.restored" if restore else "branch.archived", b.name)
            return True

    def decisions(self, token):
        with self.sessions.begin() as s:
            self._platform(s, token)
            return [{"id": d.id, "organisatie": s.get(Organization, d.organization_id).name, "vestiging": s.get(Branch, d.branch_id).name if d.branch_id else "—", "beoordelaar": reviewer.email, "van": d.previous_status, "naar": d.status, "reden": d.reason, "tijd": d.occurred_at} for d, reviewer in s.execute(select(ApprovalDecision, User).join(User, User.id == ApprovalDecision.reviewer_id).order_by(ApprovalDecision.id.desc()))]

    def platform_users(self, token):
        with self.sessions.begin() as s:
            self._platform(s, token, owner=True)
            return [{"id": u.id, "naam": u.name, "email": u.email, "platformeigenaar": u.platform_owner} for u in s.scalars(select(User).where(User.platform_admin.is_(True)))]

    def delegate_platform(self, token, email, enabled):
        email = email_address(email)
        if type(enabled) is not bool:
            raise ValueError("Ongeldige machtiging.")
        with self.sessions.begin() as s:
            u = self._platform(s, token, owner=True)
            target = s.scalar(select(User).where(User.email == email).with_for_update())
            if not target:
                raise ValueError("Registreer eerst een persoonlijk account voor deze gebruiker.")
            if target.platform_owner:
                raise Denied("De platformeigenaar kan niet worden ingetrokken.")
            target.platform_admin = enabled
            self._audit(s, u, None, "platform.delegated", f"user={target.id}; enabled={enabled}")

    def review_shift(self, token, branch_id, entry_id, version, action, reason="", start=None, end=None):
        if action not in ("approve", "correct"):
            raise ValueError("Ongeldige shiftactie.")
        reason = reason.strip()
        if len(reason) > 500 or (action == "correct" and not reason):
            raise ValueError("Een correctie vereist een reden van maximaal 500 tekens.")
        with self.sessions.begin() as s:
            actor = self._actor(s, token)
            self._access(s, actor, branch_id, admin=True, lock=True)
            uid = s.scalar(select(WorkEntry.user_id).where(WorkEntry.id == entry_id, WorkEntry.branch_id == branch_id))
            if uid is None:
                raise Denied("Shift niet gevonden in deze vestiging.")
            s.execute(text("SELECT pg_advisory_xact_lock(793125043, :uid)"), {"uid": uid})
            entry = s.scalar(select(WorkEntry).where(WorkEntry.id == entry_id, WorkEntry.branch_id == branch_id).with_for_update())
            if not entry:
                raise Denied("Shift niet gevonden in deze vestiging.")
            if entry.user_id == actor.id:
                raise Denied("Laat een andere bevoegde beheerder je eigen shift controleren.")
            if entry.version != version:
                raise ValueError("Deze shift is ondertussen gewijzigd. Ververs het overzicht.")
            old_start, old_end, old_status = entry.started_at, entry.ended_at, entry.review_status
            if action == "approve":
                if entry.ended_at is None:
                    raise ValueError("Een lopende shift kan niet worden goedgekeurd. Sluit of corrigeer deze eerst.")
                if entry.review_status == "approved":
                    raise ValueError("Deze shift is al goedgekeurd.")
                entry.review_status, entry.reviewed_by, entry.reviewed_at = "approved", actor.id, now()
            else:
                if not all(isinstance(v, datetime) and v.tzinfo is not None and v.utcoffset() is not None for v in (start, end)):
                    raise ValueError("Geef begin- en eindtijd met tijdzone op.")
                if end <= start or end > now():
                    raise ValueError("Einde moet na begin liggen en mag niet in de toekomst liggen.")
                # Serialize all corrections for the same employee, including other branches.
                s.execute(text("SELECT pg_advisory_xact_lock(793125043, :uid)"), {"uid": entry.user_id})
                overlap = s.scalar(select(WorkEntry.id).where(WorkEntry.user_id == entry.user_id, WorkEntry.id != entry.id, WorkEntry.started_at < end, or_(WorkEntry.ended_at.is_(None), WorkEntry.ended_at > start)))
                if overlap:
                    raise ValueError("Deze tijden overlappen met een andere shift van deze medewerker.")
                if start == old_start and end == old_end:
                    raise ValueError("De tijden zijn niet gewijzigd.")
                entry.started_at, entry.ended_at = start, end
                entry.review_status, entry.reviewed_by, entry.reviewed_at = "pending", None, None
            entry.version += 1
            log = ShiftReview(entry_id=entry.id, reviewer_id=actor.id, action=action, reason=reason, old_start=old_start, old_end=old_end, new_start=entry.started_at, new_end=entry.ended_at, previous_status=old_status, created_at=now())
            s.add(log)
            s.flush()
            self._audit(s, actor, branch_id, "shift." + action, f"entry={entry.id}; review={log.id}")
            return log.id

    def shift_history(self, token, branch_id, entry_id):
        with self.sessions.begin() as s:
            actor = self._actor(s, token)
            self._access(s, actor, branch_id)
            entry = s.scalar(select(WorkEntry).where(WorkEntry.id == entry_id, WorkEntry.branch_id == branch_id))
            if not entry:
                raise Denied("Shift niet gevonden.")
            if entry.user_id != actor.id:
                self._access(s, actor, branch_id, admin=True)
            return [{"actie": r.action, "reden": r.reason, "beoordelaar": reviewer.name, "tijd": r.created_at, "oud_begin": r.old_start, "oud_einde": r.old_end, "nieuw_begin": r.new_start, "nieuw_einde": r.new_end} for r, reviewer in s.execute(select(ShiftReview, User).join(User, User.id == ShiftReview.reviewer_id).where(ShiftReview.entry_id == entry.id).order_by(ShiftReview.id.desc()))]

    def _public_url(self):
        url = os.getenv('APP_BASE_URL', '').strip().rstrip('/')
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Stel eerst APP_BASE_URL in op het HTTPS-adres van deze app.')
        return url

    def _password(self, password):
        if not isinstance(password, str) or not 12 <= len(password) <= 128:
            raise ValueError('Gebruik een wachtwoord van 12 tot 128 tekens.')
        return hasher.hash(password)

    def invite(self, token, branch_id, email):
        email, base = email_address(email), self._public_url()
        with self.sessions.begin() as s:
            actor = self._actor(s, token)
            branch = self._access(s, actor, branch_id, admin=True, lock=True)
            s.execute(text('SELECT pg_advisory_xact_lock(793125044, :key)'), {'key': int(digest(email)[:7],16)})
            for old in s.scalars(select(AccountToken).where(AccountToken.purpose=='invite', AccountToken.branch_id==branch_id, AccountToken.email==email, AccountToken.consumed_at.is_(None))):
                old.consumed_at = now()
            raw = secrets.token_urlsafe(32)
            s.add(AccountToken(token_hash=digest(raw),purpose='invite',email=email,branch_id=branch_id,created_by=actor.id,expires_at=now()+timedelta(days=7)))
            url = base + '?' + urlencode({'invite':raw})
            s.add(Notification(recipient=email,subject='Uitnodiging voor ShiftFlow',body=f'Je bent uitgenodigd als medewerker bij {branch.name}. Open binnen 7 dagen: {url}\nBestaande gebruikers moeten met hun eigen account inloggen.'))
            self._audit(s,actor,branch_id,'account.invited',f'email={email}')
            return url

    def accept_invite(self, raw, token=None, name=None, password=None, language="nl"):
        if language not in ("nl","fr","en","de","es"):
            raise ValueError("Ongeldige taalkeuze.")
        with self.sessions.begin() as s:
            invitation = s.scalar(select(AccountToken).where(AccountToken.token_hash==digest(raw), AccountToken.purpose=='invite').with_for_update())
            if not invitation or invitation.consumed_at or invitation.expires_at <= now():
                raise Denied('Uitnodiging ongeldig, verlopen of al gebruikt.')
            inviter = s.get(User,invitation.created_by)
            if not inviter or not inviter.is_active:
                raise Denied('De uitnodiging is niet meer geldig.')
            self._access(s,inviter,invitation.branch_id,admin=True,lock=True)
            account = s.scalar(select(User).where(User.email==invitation.email))
            if account:
                actor = self._actor(s,token)
                if actor.id != account.id:
                    raise Denied('Log in met het e-mailadres waarop je bent uitgenodigd.')
            else:
                if token:
                    raise Denied('Log uit om een nieuw account voor deze uitnodiging aan te maken.')
                account = User(email=invitation.email,name=clean(name or '', 'Naam'),password_hash=self._password(password),language=language)
                s.add(account)
                s.flush()
            membership = s.get(Membership,(invitation.branch_id,account.id))
            if membership is None:
                s.add(Membership(branch_id=invitation.branch_id,user_id=account.id,role='employee'))
            elif membership.role=='revoked':
                membership.role='employee'
            invitation.consumed_at=now()
            self._audit(s,account,invitation.branch_id,'invitation.accepted',f'inviter={inviter.id}')
            return account.id

    def request_password_reset(self, email):
        email = email_address(email)
        if os.getenv('EMAIL_DELIVERY_ENABLED') != '1':
            raise ValueError('Wachtwoordherstel per e-mail is nog niet ingesteld. Neem contact op met de platformeigenaar.')
        base = self._public_url()
        with self.sessions.begin() as s:
            key=digest('reset:'+email)
            s.execute(insert(LoginLimit).values(key=key,failures=0,window_start=now()).on_conflict_do_nothing())
            limit=s.scalar(select(LoginLimit).where(LoginLimit.key==key).with_for_update())
            if now()-limit.window_start>=timedelta(minutes=15):
                limit.failures,limit.window_start=0,now()
            if limit.failures>=3:
                return True
            limit.failures+=1
            account=s.scalar(select(User).where(User.email==email,User.is_active.is_(True)))
            if account:
                for old in s.scalars(select(AccountToken).where(AccountToken.purpose=='reset',AccountToken.user_id==account.id,AccountToken.consumed_at.is_(None))):
                    old.consumed_at=now()
                raw=secrets.token_urlsafe(32)
                s.add(AccountToken(token_hash=digest(raw),purpose='reset',email=email,user_id=account.id,expires_at=now()+timedelta(hours=1)))
                url=base+'?'+urlencode({'reset':raw})
                s.add(Notification(recipient=email,subject='ShiftFlow wachtwoord herstellen',body=f'Gebruik binnen een uur deze eenmalige link: {url}\nNiet aangevraagd? Negeer dit bericht.'))
            return True

    def reset_password(self, raw, password):
        hashed=self._password(password)
        with self.sessions.begin() as s:
            reset=s.scalar(select(AccountToken).where(AccountToken.token_hash==digest(raw),AccountToken.purpose=='reset').with_for_update())
            if not reset or reset.consumed_at or reset.expires_at<=now():
                raise Denied('Herstellink ongeldig, verlopen of al gebruikt.')
            key=digest(reset.email)
            s.execute(insert(LoginLimit).values(key=key,failures=0,window_start=now()).on_conflict_do_nothing())
            s.scalar(select(LoginLimit).where(LoginLimit.key==key).with_for_update())
            account=s.scalar(select(User).where(User.id==reset.user_id).with_for_update())
            if not account or not account.is_active:
                raise Denied('Herstellink ongeldig, verlopen of al gebruikt.')
            account.password_hash=hashed
            for row in s.scalars(select(AccountToken).where(AccountToken.purpose=='reset',AccountToken.user_id==account.id,AccountToken.consumed_at.is_(None))):
                row.consumed_at=now()
            s.execute(delete(AuthSession).where(AuthSession.user_id==account.id))
            s.execute(delete(LoginLimit).where(LoginLimit.key==digest(account.email)))
            self._audit(s,account,None,'password.reset','Alle bestaande sessies ingetrokken')
            return True

    def change_password(self, token, current, password):
        hashed=self._password(password)
        with self.sessions.begin() as s:
            actor=self._actor(s,token)
            try:
                hasher.verify(actor.password_hash,current)
            except VerificationError as exc:
                raise Denied('Huidig wachtwoord onjuist.') from exc
            actor.password_hash=hashed
            s.execute(delete(AuthSession).where(AuthSession.user_id==actor.id))
            self._audit(s,actor,None,'password.changed','Alle bestaande sessies ingetrokken')
            return True

    def _account_actions(self, s, actor, target):
        owner = s.scalar(select(Organization.id).where(Organization.owner_id == target.id)) is not None
        blocked = None
        if target.id == actor.id:
            blocked = 'Dit is je eigen account. Je kunt jezelf niet deactiveren of verwijderen.'
        elif target.platform_owner:
            blocked = 'De platformeigenaar is beschermd en kan niet worden gedeactiveerd of verwijderd.'
        elif target.platform_admin and not actor.platform_owner:
            blocked = 'Alleen de platformeigenaar kan andere platformbeheerders beheren.'
        elif owner and target.is_active:
            blocked = 'Dit account is eigenaar van een organisatie. Blokkeer de organisatie via Aanvragen; eigendomsoverdracht is nog niet beschikbaar.'
        references = [
            select(WorkEntry.id).where(or_(WorkEntry.user_id == target.id, WorkEntry.reviewed_by == target.id)),
            select(ShiftPlan.id).where(or_(ShiftPlan.user_id == target.id, ShiftPlan.created_by == target.id)),
            select(Audit.id).where(Audit.actor_id == target.id),
            select(ApprovalDecision.id).where(ApprovalDecision.reviewer_id == target.id),
            select(Organization.id).where(Organization.reviewed_by == target.id),
            select(Branch.id).where(or_(Branch.reviewed_by == target.id, Branch.archived_by == target.id)),
            select(ShiftReview.id).where(ShiftReview.reviewer_id == target.id),
            select(AccountToken.token_hash).where(or_(AccountToken.user_id == target.id, AccountToken.created_by == target.id, AccountToken.email == target.email)),
        ]
        delete_reason = blocked
        if not delete_reason and (owner or target.platform_admin):
            delete_reason = 'Eigenaar- en platformbeheerderaccounts kunnen niet definitief worden verwijderd.'
        if not delete_reason and any(s.scalar(q.limit(1)) is not None for q in references):
            delete_reason = 'Dit account heeft werkuren, planning of beveiligingshistoriek. Deactiveer het account om de toegang te stoppen en de historiek te bewaren.'
        return {'can_manage': blocked is None, 'manage_reason': blocked, 'can_delete': delete_reason is None, 'delete_reason': delete_reason}

    def accounts(self, token):
        with self.sessions.begin() as s:
            actor = self._platform(s, token)
            return [{'id': u.id, 'naam': u.name, 'email': u.email, 'actief': u.is_active,
                     'platformbeheerder': u.platform_admin, 'platformeigenaar': u.platform_owner,
                     **self._account_actions(s, actor, u)} for u in s.scalars(select(User).order_by(User.name, User.id))]

    def delete_unused_account(self, token, user_id):
        try:
            with self.sessions.begin() as s:
                actor = self._platform(s, token)
                target = s.get(User, user_id)
                if not target:
                    raise ValueError('Account bestaat niet meer. Ververs het overzicht.')
                org_ids = list(s.scalars(select(Organization.id).join(Branch, Branch.organization_id == Organization.id).join(Membership, Membership.branch_id == Branch.id).where(Membership.user_id == user_id).distinct().order_by(Organization.id)))
                for oid in org_ids:
                    s.scalar(select(Organization).where(Organization.id == oid).with_for_update())
                # Match login lock order so an in-progress login cannot recreate a session.
                key = digest(target.email)
                s.execute(insert(LoginLimit).values(key=key, failures=0, window_start=now()).on_conflict_do_nothing())
                s.scalar(select(LoginLimit).where(LoginLimit.key == key).with_for_update())
                target = s.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
                if not target:
                    raise ValueError('Account bestaat niet meer. Ververs het overzicht.')
                s.execute(text('SELECT pg_advisory_xact_lock(793125043, :uid)'), {'uid': user_id})
                policy = self._account_actions(s, actor, target)
                if not policy['can_delete']:
                    raise Denied(policy['delete_reason'])
                s.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
                s.execute(delete(Membership).where(Membership.user_id == user_id))
                s.delete(target)
                s.flush()
                s.execute(delete(LoginLimit).where(LoginLimit.key == key))
                self._audit(s, actor, None, 'account.deleted', f'user={user_id}; unused account removed')
                return True
        except IntegrityError as exc:
            raise ValueError('Het account is ondertussen in gebruik genomen. Ververs het overzicht; historische gegevens worden niet verwijderd.') from exc

    def set_account_active(self, token, user_id, enabled, reason):
        if type(enabled) is not bool:
            raise ValueError('Ongeldige status.')
        reason=clean(reason,'Reden',300)
        with self.sessions.begin() as s:
            actor=self._platform(s,token)
            target=s.get(User,user_id)
            if not target:
                raise ValueError('Account niet gevonden.')
            if target.id==actor.id or target.platform_owner or (target.platform_admin and not actor.platform_owner):
                raise Denied('Je mag dit account niet deactiveren of heractiveren.')
            if not enabled and s.scalar(select(Organization.id).where(Organization.owner_id==target.id)):
                raise Denied('Deze gebruiker is organisatie-eigenaar. Blokkeer de organisatie; accountdeactivering vereist eerst eigendomsoverdracht.')
            orgs=select(Organization.id).join(Branch,Branch.organization_id==Organization.id).join(Membership,Membership.branch_id==Branch.id).where(Membership.user_id==target.id).distinct().order_by(Organization.id)
            ids=list(s.scalars(orgs))
            for oid in ids:
                s.scalar(select(Organization).where(Organization.id==oid).with_for_update())
            target=s.scalar(select(User).where(User.id==target.id).with_for_update().execution_options(populate_existing=True))
            if target.id==actor.id or target.platform_owner or (target.platform_admin and not actor.platform_owner):
                raise Denied('Je mag dit account niet deactiveren of heractiveren.')
            s.execute(text('SELECT pg_advisory_xact_lock(793125043, :uid)'),{'uid':target.id})
            if target.is_active==enabled:
                raise ValueError('Dit account heeft deze status al.')
            target.is_active=enabled
            if not enabled:
                for entry in s.scalars(select(WorkEntry).where(WorkEntry.user_id==target.id,WorkEntry.ended_at.is_(None)).with_for_update()):
                    entry.ended_at=now()
                    entry.version+=1
                    self._audit(s,actor,entry.branch_id,'clock.closed_by_deactivation',f'entry={entry.id}; user={target.id}')
                s.execute(delete(AuthSession).where(AuthSession.user_id==target.id))
            self._audit(s,actor,None,'account.reactivated' if enabled else 'account.deactivated',f'user={target.id}; reason={reason}')
            return True

    def plans(self, token, branch_id, team=False):
        with self.sessions.begin() as s:
            actor=self._actor(s,token)
            self._access(s,actor,branch_id,admin=team)
            q=select(ShiftPlan,User.name).join(User,User.id==ShiftPlan.user_id).where(ShiftPlan.branch_id==branch_id)
            if not team:
                q=q.where(ShiftPlan.user_id==actor.id)
            result=[]
            for plan,name in s.execute(q.order_by(ShiftPlan.starts_at)):
                entry=s.scalar(select(WorkEntry).where(WorkEntry.plan_id==plan.id))
                result.append({'id':plan.id,'user_id':plan.user_id,'name':name,'start':plan.starts_at,'end':plan.ends_at,'status':plan.status,'note':plan.note,'version':plan.version,'entry_id':entry.id if entry else None,'actual_start':entry.started_at if entry else None,'actual_end':entry.ended_at if entry else None})
            return result

    def save_plan(self, token, branch_id, user_id, start, end, note='', plan_id=None, version=None):
        if not all(isinstance(v,datetime) and v.tzinfo is not None and v.utcoffset() is not None for v in (start,end)) or end<=start:
            raise ValueError('Geef geldige begin- en eindtijden met tijdzone; einde moet na begin liggen.')
        if end<=now():
            raise ValueError('Plan een shift die nog niet volledig voorbij is.')
        note=note.strip()
        if len(note)>500:
            raise ValueError('Gebruik maximaal 500 tekens voor de opmerking.')
        with self.sessions.begin() as s:
            actor=self._actor(s,token)
            self._access(s,actor,branch_id,admin=True,lock=True)
            s.execute(text('SELECT pg_advisory_xact_lock(793125043, :uid)'),{'uid':user_id})
            membership=s.get(Membership,(branch_id,user_id))
            user=s.get(User,user_id)
            if not membership or membership.role=='revoked' or not user or not user.is_active:
                raise ValueError('Kies een actieve medewerker van deze vestiging.')
            plan=None
            if plan_id is not None:
                plan=s.scalar(select(ShiftPlan).where(ShiftPlan.id==plan_id,ShiftPlan.branch_id==branch_id).with_for_update())
                if not plan:
                    raise Denied('Geen toegang tot deze geplande shift.')
                if plan.version!=version or plan.status!='scheduled':
                    raise ValueError('De planning is gewijzigd; ververs het overzicht.')
                if plan.user_id!=user_id:
                    raise ValueError('Annuleer de shift en maak een nieuwe om de medewerker te wijzigen.')
                if s.scalar(select(WorkEntry.id).where(WorkEntry.plan_id==plan.id)):
                    raise ValueError('Deze shift heeft al een tijdregistratie en kan niet meer worden verplaatst.')
            overlap=select(ShiftPlan.id).where(ShiftPlan.user_id==user_id,ShiftPlan.status=='scheduled',ShiftPlan.starts_at<end,ShiftPlan.ends_at>start)
            if plan:
                overlap=overlap.where(ShiftPlan.id!=plan.id)
            if s.scalar(overlap):
                raise ValueError('Deze medewerker is op dit tijdstip al ingepland, mogelijk in een andere vestiging.')
            old=f'{plan.starts_at.isoformat()}..{plan.ends_at.isoformat()}' if plan else 'nieuw'
            if plan:
                plan.starts_at,plan.ends_at,plan.note=start,end,note
                plan.version+=1
            else:
                plan=ShiftPlan(branch_id=branch_id,user_id=user_id,starts_at=start,ends_at=end,note=note,created_by=actor.id)
                s.add(plan)
            s.flush()
            self._audit(s,actor,branch_id,'plan.saved',f'plan={plan.id}; oud={old}; nieuw={start.isoformat()}..{end.isoformat()}')
            return plan.id

    def cancel_plan(self,token,branch_id,plan_id,version,reason):
        reason=clean(reason,'Reden',250)
        with self.sessions.begin() as s:
            actor=self._actor(s,token)
            self._access(s,actor,branch_id,admin=True,lock=True)
            plan=s.scalar(select(ShiftPlan).where(ShiftPlan.id==plan_id,ShiftPlan.branch_id==branch_id).with_for_update())
            if not plan:
                raise Denied('Geen toegang tot deze geplande shift.')
            if plan.version!=version or plan.status!='scheduled':
                raise ValueError('De planning is gewijzigd; ververs het overzicht.')
            if s.scalar(select(WorkEntry.id).where(WorkEntry.plan_id==plan.id)):
                raise ValueError('Een shift met tijdregistratie kan niet worden geannuleerd.')
            plan.status='cancelled'
            plan.version+=1
            self._audit(s,actor,branch_id,'plan.cancelled',f'plan={plan.id}; reason={reason}')
            return True

    def alerts(self,token,branch_id,team=False):
        # Uses the same fresh branch and employee authorization as the underlying views.
        entries=self.entries(token,branch_id,team=team)
        plans=self.plans(token,branch_id,team=team)
        snapshot=now()
        byid={p['id']:p for p in plans}
        result=[]
        for entry in entries:
            plan=byid.get(entry['plan_id'])
            if entry['end'] is None:
                if plan and snapshot>plan['end']+timedelta(minutes=15):
                    result.append({'type':'uitklokken','medewerker':entry['name'],'melding':'Nog ingeklokt, meer dan 15 minuten na geplande eindtijd.','shift':entry['id']})
                elif snapshot-entry['start']>timedelta(hours=12):
                    result.append({'type':'uitklokken','medewerker':entry['name'],'melding':'Meer dan 12 uur ingeklokt. Controleer of uitklokken is vergeten.','shift':entry['id']})
            elif entry['review_status']=='pending' and team:
                result.append({'type':'controle','medewerker':entry['name'],'melding':'Afgesloten shift wacht op controle.','shift':entry['id']})
        return result

    def set_language(self, token, language):
        if language not in ('nl','fr','en','de','es'):
            raise ValueError('Ongeldige taalkeuze.')
        with self.sessions.begin() as s:
            actor=self._actor(s,token)
            actor.language=language
            return True
