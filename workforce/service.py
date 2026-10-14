"""Every public operation authenticates and authorizes in the same transaction."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import select, or_, text, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert
from workforce.models import User, Organization, Branch, Membership, WorkEntry, AuthSession, LoginLimit, Audit, ApprovalDecision, Notification, ShiftReview

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

    def register(self, email, name, password, organization=None, chain=None, branch=None, address=None, phone=None):
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
                u = User(email=email, name=name, password_hash=hasher.hash(password), platform_admin=False)
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
                success = hasher.verify(u.password_hash if u else DUMMY_HASH, password) and u is not None
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
        u = s.scalar(select(User).join(AuthSession).where(AuthSession.token_hash == digest(token), AuthSession.expires_at > now()))
        if not u:
            raise Denied("Sessie verlopen. Log opnieuw in.")
        return u

    def identity(self, token):
        with self.sessions.begin() as s:
            u = self._actor(s, token)
            return {"id": u.id, "name": u.name, "email": u.email, "platform_admin": u.platform_admin, "platform_owner": u.platform_owner}

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
        if org.status != "approved" or b.status != "approved":
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
            q = select(Branch, Organization).join(Organization)
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
            if not target:
                raise ValueError("Gebruiker niet gevonden.")
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
            return [{"id": member.id, "name": member.name, "email": member.email, "role": m.role} for member, m in s.execute(select(User, Membership).join(Membership).where(Membership.branch_id == branch_id).order_by(User.name))]

    def clock_in(self, token, branch_id):
        try:
            with self.sessions.begin() as s:
                u = self._actor(s, token)
                self._access(s, u, branch_id, lock=True)
                s.execute(text("SELECT pg_advisory_xact_lock(793125043, :uid)"), {"uid": u.id})
                m = s.get(Membership, (branch_id, u.id))
                if not m or m.role == "revoked":
                    raise Denied("Je bent geen medewerker van deze vestiging.")
                e = WorkEntry(branch_id=branch_id, user_id=u.id, started_at=now())
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
            return [{"id": e.id, "user_id": e.user_id, "name": name, "start": e.started_at, "end": e.ended_at, "review_status": e.review_status, "version": e.version, "reviewed_by": e.reviewed_by, "reviewed_at": e.reviewed_at} for e, name in s.execute(q.order_by(WorkEntry.started_at.desc()))]

    def audit(self, token, branch_id):
        with self.sessions.begin() as s:
            u = self._actor(s, token)
            self._access(s, u, branch_id, admin=True)
            return [{"tijd": a.created_at, "actor": a.actor_id, "actie": a.action, "detail": a.detail} for a in s.scalars(select(Audit).where(Audit.branch_id == branch_id).order_by(Audit.id.desc()).limit(100))]

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
        if not u.platform_admin or (owner and not u.platform_owner):
            raise Denied("Alleen bevoegde platformbeheerders hebben toegang.")
        return u

    def applications(self, token):
        with self.sessions.begin() as s:
            self._platform(s, token)
            result = []
            for org, responsible in s.execute(select(Organization, User).join(User, User.id == Organization.owner_id).order_by(Organization.id)):
                for entity in [org, *s.scalars(select(Branch).where(Branch.organization_id == org.id).order_by(Branch.id))]:
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
