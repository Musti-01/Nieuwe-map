# ShiftFlow — personeels- en tijdregistratie MVP

Een Streamlit-app met Python 3.12 en PostgreSQL 16 voor onafhankelijke franchisenemers en meerdere vestigingen. Bestaande HTML-bestanden blijven behouden; `app.py` is de SaaS-ingang. Geen vaste keten, accounts of medewerkers.

## Deze versie

- Registratieaanvragen voor organisaties en vestigingen met adres, verantwoordelijke en contactgegevens. Iedere aanvraag begint als **In afwachting**.
- Apart platformdashboard met goedkeuren, weigeren, blokkeren, opnieuw activeren en besluitgeschiedenis.
- Alleen de platformeigenaar kan bestaande gebruikers expliciet machtigen als platformbeheerder.
- Extra vestigingen voor dezelfde organisatie-eigenaar, ieder met eigen verplichte goedkeuring.
- Persoonlijke registratie van medewerkers, beveiligde login, uitloggen en server-side sessies van maximaal 8 uur.
- Eenmalige lokale bootstrap voor de platformeigenaar.
- Eigenaar selecteert bestaande gebruikers via exact e-mailadres en kent vestigingsadminrechten toe. Eén gebruiker kan meerdere vestigingen beheren.
- Vestigingsadmin koppelt medewerkers; alleen eigenaar/platformbeheerder wijzigt adminrechten. Intrekken werkt bij de volgende serveractie, ook voor bestaande sessies.
- In-/uitklokken met serverklok en databasegarantie van maximaal één actieve dienst per gebruiker, over alle vestigingen heen.
- Eigen uren en dashboard per dag/week/maand, actieve medewerkers, teambeheer en auditlog van rolwijzigingen en klokacties.
- Organisatie-eigenaar kan schakelen tussen eigen vestigingen. Platformbeheerder kan alle organisaties en vestigingen bekijken en beheren via hetzelfde rechtenbeheer.

Pauzes, correcties met auditlog, CSV/Excel-export, vergelijkingsrapporten, logo-/kleurenbeheer, abonnementenbeheer en betalingen zijn **nog niet geïmplementeerd**. Velden voor keten, organisatiekleuren en vestigingspakket bereiden uitbreiding voor; ze leveren nog geen pakketbeperkingen of brandinginstellingen. De MVP is een testbare basis, geen reeds gelanceerde commerciële dienst.

## Snel lokaal / cloud testen

Vereist: Python 3.12, Docker met Compose. Gebruik de bestaande checkout; cloudtaken zijn al geïsoleerd, maak geen extra Git-worktree.

```bash
cd /workspace/Nieuwe-map  # lokaal: pad naar jouw checkout
./scripts/install.sh
./scripts/start.sh
```

De installatiestap gebruikt een volledig gepind lockbestand met pakket-hashes. Het opstartscript maakt alleen bij ontbrekende configuratie een genegeerde `.env` aan met een willekeurig lokaal databasewachtwoord. Compose start PostgreSQL; de data staan in `.local/postgres` buiten Git. Vervolgens controleert het script de database, voert migraties uit en start Streamlit op poort 8501. Herhaalbaar: geen reset of overschrijven van bestaande configuratie. Op je **eigen computer** open je `http://localhost:8501`. De cloud-onboardinginterface biedt geen live localhost-preview; gebruik de schermafbeeldingen of deploy naar een externe host om zelf online te testen.

Registreer eerst jouw persoonlijke platformaccount (organisatiecheckbox uit) en voer de bootstrap hieronder uit. Registreer daarna een organisatie met eerste vestiging in een andere browser. Keur als platformeigenaar in **Platformdashboard** eerst de organisatie en daarna de vestiging goed. Vóór beide goedkeuringen zijn klokacties, teambeheer en rapporten geblokkeerd. Registreer een medewerker in een andere browser/incognitovenster, met de organisatiecheckbox uit. Zoek de medewerker in **Team & rechten** op exact e-mailadres en wijs een rol toe. Log als medewerker in, klok in en controleer het dashboard als beheerder; klok daarna uit. Een medewerker zonder toewijzing ziet geen vestigingsgegevens.

`.env.example` bevat uitsluitend placeholders. Voor een handmatig beheerde lokale Compose-database voeg je `POSTGRES_PASSWORD` en `LOCAL_DATABASE=1` toe; gebruik hetzelfde wachtwoord in `DATABASE_URL`. Voor een beheerde database stel je `DATABASE_URL` veilig bij de host in en gebruik je geen lokale Compose-database.

### Platformeigenaar veilig instellen

1. Registreer jouw persoonlijke account via de app, zonder organisatieaanvraag.
2. Voer vanuit een vertrouwde beheershell met toegang tot de database uit:

```bash
.venv/bin/python -m workforce.bootstrap --email jouw-adres@example.com
```

De procedure promoveert een bestaand account tot platformeigenaar en platformbeheerder. Een PostgreSQL advisory lock maakt bootstrap eenmalig, ook bij gelijktijdige uitvoering. Zodra er een platformbeheerder bestaat, is bootstrap gesloten. De procedure is niet bereikbaar via de webinterface. Er bestaat geen standaardaccount, bootstrapwachtwoord of publieke adminregistratie. Database-/shelltoegang is een beheersbevoegdheid. Herstel bij verlies van dat account is bewust geen openbare functie van deze MVP.

## Tests en migraties

Tests wissen tabellen in de opgegeven testdatabase. Gebruik uitsluitend een afzonderlijke, wegwerpbare database waarvan de naam op `_test` eindigt, nooit een klanten- of productiedatabase.

```bash
docker compose exec db createdb -U workforce workforce_test
# Stel TEST_DATABASE_URL veilig in op de overeenkomstige workforce_test URL.
.venv/bin/python -m pytest -q
.venv/bin/alembic upgrade head
.venv/bin/alembic check
```

`TEST_DATABASE_URL` is verplicht; zonder deze waarde stopt pytest met een fout. Tests gebruiken echte PostgreSQL-migraties, geen SQLite-vervanging. Dekking omvat verplichte goedkeuring van organisatie én vestiging, besluitgeschiedenis, blokkering/heractivering, expliciete platformmachtiging en intrekking, gelijktijdige besluiten, de optionele mailwachtrij, Argon2-hashing, login/rate limiting, sessieverloop/uitloggen, rollen, tenantisolatie, meerdere admins per vestiging, directe intrekking, auditregistratie, uren, DST en gelijktijdig inklokken. GitHub Actions voert dezelfde suite uit bij push en PR. De CI-configuratie is toegevoegd maar de GitHub-run is pas uitgevoerd na een push.

Nieuwe schemawijzigingen krijgen een nieuwe migratie. Wijzig geen reeds gebruikte migratie:

```bash
.venv/bin/alembic revision --autogenerate -m "beschrijving"
# Beoordeel de gegenereerde migratie en test haar op een afzonderlijke database.
.venv/bin/alembic upgrade head
```

## Codeverschillen bekijken en voortbouwen

De huidige wijzigingen staan in de werkmap en zijn niet automatisch naar GitHub gepusht. Bekijk nieuwe bestanden in je editor en `git status --short`. Om alle wijzigingen, inclusief nieuwe bestanden, als Git-diff te bekijken:

```bash
git add .
git diff --cached --stat
git diff --cached
# Pas na eigen beoordeling:
git commit -m "Add workforce SaaS MVP"
git push origin master
```

Controleer vóór commit dat `.env`, `.local`, `.venv` en secrets uitgesloten blijven. De aangeleverde reviewpatch bevat de nieuwe projectbestanden. Volgende opdrachten bouwen verder op `workforce/`, `app.py`, de bestaande migraties en tests; herbouw het project niet opnieuw.

## Streamlit Community Cloud

Zie [de stapsgewijze handleiding](docs/STREAMLIT_DEPLOY.md). Kies `cloud_app.py` als entrypoint. Databasegegevens horen uitsluitend in Streamlit Secrets; migraties starten automatisch en zijn geserialiseerd.

## Deployment met duurzame PostgreSQL

Gebruik een host die een langlopende Python- of Docker-service en WebSockets ondersteunt (bijvoorbeeld een containerhost), met **een aparte beheerde PostgreSQL-database** en backups. Gebruik de tijdelijke cloud-testdatabase niet als klantendatabase. Bewaar geen klantgegevens op een vluchtige appcontainer.

1. Publiceer na beoordeling de code in jouw GitHub-repository en koppel die aan de host.
2. Stel `DATABASE_URL` in via het secretbeheer van de host, bijvoorbeeld een `postgresql+psycopg://...` URL met de door de databaseprovider vereiste TLS-opties. Gebruik `sslmode=verify-full` en een vertrouwde CA waar ondersteund; volg de providerinstructies. Commit nooit echte URL's, wachtwoorden of CA-private sleutels. Stel `APP_TIMEZONE=Europe/Brussels` in.
3. Python-host: installeer met `pip install --require-hashes -r requirements.lock`. Docker-host: bouw met de meegeleverde `Dockerfile`.
4. Voer `alembic upgrade head` als eenmalige releaseopdracht uit vóór de appstart. Het Docker-CMD voert bewust geen parallelle migraties uit.
5. Start `streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT` (Docker standaard 8501; override CMD als de host een andere poort vereist).
6. Publiceer via HTTPS met WebSocket-ondersteuning. Proxy de volledige Streamlit-service, inclusief `/_stcore/stream`. Houd CORS en XSRF aan; beperk database- en shelltoegang. Healthcheck: `/_stcore/health` moet `ok` geven, gevolgd door een echte registratie/login/kloktest.
7. Registreer en bootstrap jouw platformeigenaar via een vertrouwde shell. Controleer tenantisolatie met twee testorganisaties en herstelbaarheid van databasebackups voordat klanten de dienst gebruiken.

Streamlit-sessies gebruiken een per-verbinding token in server-side `session_state`; de database bewaart uitsluitend de tokenhash. Browserherladen/opnieuw verbinden kan opnieuw inloggen vereisen. Gebruik één appinstantie of sticky WebSocket-sessies bij schalen. Streamlit heeft geen volwaardige persistente SaaS-authcookie in deze MVP.

Voor commerciële lancering ontbreken onder andere e-mailverificatie, wachtwoordherstel, MFA voor beheerders, operationele registratie-/IP-rate-limiting, monitoring en een privacy-/retentiebeleid. Loginpogingen zijn nu begrensd per e-mailadres (vijf fouten per 15 minuten); dit vervangt geen platformbrede misbruikbescherming. Deze uitbreidingen worden niet zonder volgende opdracht ingebouwd.

## Architectuur en grenzen

- `workforce/models.py`: gebruikers, organisaties, vestigingen, lidmaatschappen, diensten, sessies en audit.
- `workforce/service.py`: de enige interface voor UI-datatoegang; iedere actie controleert sessie en actuele bevoegdheden in een transactie. Identiteiten/rollen uit widgets zijn nooit autorisatie.
- `workforce/reports.py`: periodegrenzen in lokale tijd, duur in UTC; diensten over middernacht worden op de periodegrens afgesneden.
- `migrations/`: Alembic-schema met constraints, foreign keys en een gedeeltelijk unieke index voor actieve diensten.
- `tests/`: integratietests tegen PostgreSQL.

Toegang wordt op applicatieniveau in de servicelaag afgedwongen; PostgreSQL RLS is niet ingeschakeld. Directe SQL-toegang is alleen voor vertrouwde operators, niet voor klanten. De databasegebruiker mag nooit aan een vestiging worden verstrekt. Een rolintrekking behoudt een ingetrokken lidmaatschapsrecord voor historische foreign keys; dit record geeft geen toegang. Actieve diensten moeten eerst afgesloten worden voordat toegang kan worden ingetrokken. Admin demotie naar medewerker behoudt diens eigen tijdregistratietoegang.

Rechtenwijzigingen en klokacties worden geaudit. Tijdcorrecties bestaan nog niet; ze moeten in een latere opdracht via een aparte geautoriseerde, geaudite servicemethode worden toegevoegd. Audit is een applicatie-audit, geen cryptografisch onveranderlijk log voor databaseoperators.

## Goedkeuringssysteem gebruiken

1. Een nieuwe eigenaar registreert bedrijfsnaam, keten, eerste vestiging, vestigingsadres, naam, e-mailadres en telefoonnummer. Zowel de organisatie als de eerste vestiging krijgen `pending` (**In afwachting**). Een extra vestiging start eveneens als `pending`.
2. De aanvrager mag inloggen en zijn aanvraagstatus zien; operationele functies zijn geblokkeerd aan de serverkant. Bij registratie worden geen platformrechten toegekend.
3. De platformeigenaar opent **Platformdashboard**, filtert aanvragen en kiest een aanvraag. Het overzicht toont bedrijfsnaam, vestiging, adres, verantwoordelijke, contactgegevens en de meest recente beoordeling.
4. Kies **Goedkeuren** of **Weigeren**, voeg toelichting toe en bevestig. Weigeren en blokkeren vereisen een reden. Keur eerst de organisatie goed, daarna iedere vestiging afzonderlijk.
5. Na beide goedkeuringen kan de eigenaar in **Team & rechten** bestaande gebruikers als vestigingsadmin aanwijzen. Vestigingsadmins krijgen nooit toegang tot het platformdashboard.
6. Via **Platformbeheerders machtigen** kan uitsluitend de platformeigenaar een bestaand account expliciet machtigen of de machtiging intrekken. Een gemachtigde platformbeheerder kan aanvragen beoordelen maar kan geen andere platformbeheerders machtigen. De platformeigenaar kan zichzelf niet demoteren.
7. Een goedgekeurde organisatie of vestiging kan **Geblokkeerd** worden en daarna **Opnieuw geactiveerd**. Een geblokkeerde organisatie blokkeert alle eigen vestigingen, zonder de afzonderlijke vestigingsstatussen te overschrijven. Bij heractiveren blijven eerder geblokkeerde vestigingen geblokkeerd; die moeten afzonderlijk worden geactiveerd.
8. Blokkering sluit actieve diensten op het blokkeertijdstip af en registreert dit in het auditlog; zo lopen uren niet onbedoeld door tijdens een blokkering. Historische registraties blijven bewaard, maar zijn operationeel pas weer toegankelijk na heractivering.

Iedere beslissing bewaart beoordelaar, tijdstip, vorige/nieuwe status en reden in `approval_decisions`; vorige beslissingen blijven zichtbaar. Dubbele/gelijktijdige besluiten worden met database-locks geserialiseerd. Een geweigerde aanvraag kan niet met de heractiveerknop goedgekeurd worden; een heraanvraagflow is nog niet geïmplementeerd.

Migratie `0002` zet ook bestaande organisaties en vestigingen op **In afwachting**, zodat geen omgeving zonder expliciete goedkeuring doorgaat. Eerdere gegevens blijven behouden. Eerder geregistreerde aanvragen kunnen geen adres/telefoon hebben; het dashboard toont dit. Als er precies één eerder gebootstrapte platformbeheerder is, wordt die de platformeigenaar. Bij afwijkende oude data met meerdere platformbeheerders wijst de migratie bewust geen eigenaar aan; dat vereist een gecontroleerde operator-migratie. Nieuwe installaties gebruiken de bootstrap.

### Optionele e-mail

Ieder besluit maakt atomair een bericht aan in de PostgreSQL-wachtrij `notifications`. Een mailfout draait het besluit niet terug. Er zijn momenteel geen SMTP-credentials geconfigureerd en er zijn **geen echte mails verstuurd**.

Configureer bij jouw deploymenthost veilig `SMTP_HOST`, `SMTP_PORT` (465 of 587), `SMTP_USER`, `SMTP_PASSWORD` en `MAIL_FROM`. Gebruik een afzender die de mailprovider toestaat, met correct ingestelde SPF/DKIM. Zet credentials nooit in Git of chat. De worker controleert TLS-certificaten: SMTP_SSL op 465 of STARTTLS op 587; onversleutelde SMTP wordt geweigerd.

```bash
.venv/bin/python -m workforce.mail
```

Plan dit commando bijvoorbeeld iedere minuut als job op dezelfde deployment met toegang tot PostgreSQL en SMTP. Per uitvoering worden maximaal 20 berichten verwerkt; mislukte berichten blijven in de wachtrij. Alleen tellingen verschijnen in de uitvoer. Gelijktijdige workers gebruiken `SKIP LOCKED`. Bij een crash na verzending maar vóór databasecommit kan een bericht nogmaals verzonden worden (at least once). Monitor mislukte pogingen en beperk retries bij langdurige providerproblemen voordat je dit commercieel gebruikt.

De mailworker is getest met een nagebootste SMTP-client, inclusief TLS en retry. Echte aflevering is pas te valideren na veilige configuratie bij jouw host. Voor de cloud-onboarding zijn de platformbindings voor HTTPS-proxysecrets geen vervanging voor een echte SMTP-login; configureer SMTP bij de uiteindelijke deploymenthost.
