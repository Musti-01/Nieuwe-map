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

Pauzes, CSV/Excel-export, vergelijkingsrapporten, logo-/kleurenbeheer, abonnementenbeheer en betalingen zijn **nog niet geïmplementeerd**. Velden voor keten, organisatiekleuren en vestigingspakket bereiden uitbreiding voor; ze leveren nog geen pakketbeperkingen of brandinginstellingen. De MVP is een testbare basis, geen reeds gelanceerde commerciële dienst.

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

Voor commerciële lancering ontbreken onder andere e-mailverificatie, geactiveerde e-mailverzending voor wachtwoordherstel, MFA voor beheerders, operationele registratie-/IP-rate-limiting, monitoring en een privacy-/retentiebeleid. Loginpogingen zijn nu begrensd per e-mailadres (vijf fouten per 15 minuten); dit vervangt geen platformbrede misbruikbescherming. Deze uitbreidingen worden niet zonder volgende opdracht ingebouwd.

## Architectuur en grenzen

- `workforce/models.py`: gebruikers, organisaties, vestigingen, lidmaatschappen, diensten, sessies en audit.
- `workforce/service.py`: de enige interface voor UI-datatoegang; iedere actie controleert sessie en actuele bevoegdheden in een transactie. Identiteiten/rollen uit widgets zijn nooit autorisatie.
- `workforce/reports.py`: periodegrenzen in lokale tijd, duur in UTC; diensten over middernacht worden op de periodegrens afgesneden.
- `migrations/`: Alembic-schema met constraints, foreign keys en een gedeeltelijk unieke index voor actieve diensten.
- `tests/`: integratietests tegen PostgreSQL.

Toegang wordt op applicatieniveau in de servicelaag afgedwongen; PostgreSQL RLS is niet ingeschakeld. Directe SQL-toegang is alleen voor vertrouwde operators, niet voor klanten. De databasegebruiker mag nooit aan een vestiging worden verstrekt. Een rolintrekking behoudt een ingetrokken lidmaatschapsrecord voor historische foreign keys; dit record geeft geen toegang. Actieve diensten moeten eerst afgesloten worden voordat toegang kan worden ingetrokken. Admin demotie naar medewerker behoudt diens eigen tijdregistratietoegang.

Rechtenwijzigingen, klokacties, shiftcorrecties en goedkeuringen worden geaudit. De shiftcorrectiehistoriek bewaart oude en nieuwe tijden, de reden en de verantwoordelijke beheerder. Audit is een applicatie-audit, geen cryptografisch onveranderlijk log voor databaseoperators.

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

## Duidelijke navigatie en shiftoverzicht

Medewerkers openen **In- en uitklokken** om een dienst te starten of af te sluiten. Bij **Mijn shiften** zien zij alleen hun eigen geklokte diensten van de geselecteerde vestiging, met datum, begin/einde, status en volledige shiftduur. Een dag-, week- of maandfilter bepaalt welke diensten zichtbaar zijn. Het urentotaal telt alleen het deel van de diensten binnen die periode; een lopende dienst telt mee tot het laatste verversen. Er is een knop **Shiften verversen** en een uitleg wanneer er nog geen diensten zijn. Dit is registratiehistoriek; toekomstige diensten staan op het aparte tabblad Planning.

Platformbeheer start met **Overzicht**, met uitleg van alle beschikbare bevoegdheden en knoppen naar **Aanvragen** en **Besluitgeschiedenis**. Uitsluitend de platformeigenaar krijgt daarnaast **Platformbeheerders**, voor het expliciet machtigen en intrekken van platformrechten. **Werkruimte → Vestigingen** opent de bestaande dashboards, teams, rollen, uren en auditlog. Via Gebruikers kunnen platformbeheerders accounts deactiveren en heractiveren. Ongebruikte, gewone accounts kunnen via Gebruikers definitief verwijderd worden; bij accounts met historiek blijft deactiveren beschikbaar.

## Shiften controleren voordat uren definitief zijn

Een medewerker kan nog steeds op een later tijdstip op Uitklokken drukken: zonder rooster of fysieke controle kan de app het werkelijke vertrekmoment niet vaststellen. Daarom krijgt iedere afgesloten shift **Wacht op controle**. Alleen een bevoegde vestigingsadmin, organisatie-eigenaar of platformbeheerder kan de shift goedkeuren. Niemand mag zijn eigen shift goedkeuren of corrigeren; vraag hiervoor een andere bevoegde beheerder.

Open de vestiging en kies **Shiften controleren**. Kies een status en shift. **Goedkeuren** accepteert de opgeslagen tijden. **Corrigeren** wijzigt begin/einde met een verplichte reden; ook een lopende, vergeten uitklokshift kan zo worden afgesloten. Toekomstige eindtijden, ongeldige intervallen en overlap met andere diensten van dezelfde medewerker worden geweigerd. Na iedere correctie wacht de shift opnieuw op goedkeuring. Gelijktijdige of verouderde wijzigingen worden geweigerd; ververs dan het overzicht.

De datum/tijdvelden gelden uitsluitend bij Corrigeren; bij Goedkeuren worden de opgeslagen tijden gebruikt. De UI vermeldt dit expliciet. Shift- en aanvraaggoedkeuring zijn aparte processen: een goedgekeurde vestiging betekent niet dat alle gewerkte uren automatisch gecontroleerd zijn.

Het dashboard toont **Goedgekeurde uren**, **Wacht op controle** en **Lopende uren (voorlopig)** apart. Medewerkers zien de status in **Mijn shiften**, met hun eigen correctiehistoriek. De klokpagina toont geregistreerde uren inclusief nog ongecontroleerde uren; alleen expliciet goedgekeurde uren zijn gecontroleerd. In de audit- en shifthistoriek staan de beoordelaar, het tijdstip, de reden en oude/nieuwe tijden.

Migratie `0003` bewaart alle bestaande werkregistraties en zet ze op **Wacht op controle**; bestaande uren worden niet stilzwijgend goedgekeurd. De migration wordt automatisch uitgevoerd bij starten van `cloud_app.py`. Dit voegt geen automatische uitklok op roostertijden en geen payroll-export toe.

## Medewerkersbeheer, planning en meldingen (migratie 0004)

### Medewerkers uitnodigen en accounts beheren

- **Team & rechten → Nieuwe medewerker uitnodigen**: voer een e-mailadres in. De app maakt een eenmalige link, geldig voor zeven dagen, en een bericht in de e-mailwachtrij. Je kunt de link zelf veilig delen. Een nieuwe uitnodiging voor hetzelfde adres en dezelfde vestiging vervangt de vorige.
- De ontvanger kan via de link een persoonlijk account aanmaken. Bestaande gebruikers loggen eerst in met het uitgenodigde e-mailadres. Acceptatie kent uitsluitend medewerkersrechten toe; bestaande adminrechten worden niet stilzwijgend gewijzigd. De uitnodiger moet bij acceptatie nog steeds bevoegd zijn en de vestiging moet operationeel zijn.
- **Mijn wachtwoord wijzigen** staat links voor ingelogde gebruikers. Het huidige wachtwoord is vereist en alle sessies worden na de wijziging ingetrokken.
- **Inloggen → Wachtwoord vergeten?** maakt een eenmalige e-maillink (één uur geldig) wanneer e-mailherstel geactiveerd is. De respons onthult niet of een e-mailadres bestaat; maximaal drie aanvragen per adres per 15 minuten. Een nieuw verzoek vervangt eerdere links. Na herstel vervallen alle sessies en wordt de loginblokkering gewist. Zonder ingestelde verzending meldt de app expliciet dat e-mailherstel nog niet beschikbaar is.
- **Platformdashboard → Gebruikers**: platformbeheerders kunnen accounts deactiveren/heractiveren met een reden en bevestiging. Deactivering trekt sessies in, blokkeert nieuwe logins en sluit actieve diensten af, met behoud van uren en auditlogs. Heractiveren herstelt bestaande vestigingsrollen; er worden geen extra rechten toegekend.
- De platformeigenaar en het eigen account zijn beschermd. Alleen de platformeigenaar kan andere platformbeheerders deactiveren. Een organisatie-eigenaar kan pas na een toekomstige eigendomsoverdrachtfunctie worden gedeactiveerd; gebruik zo nodig organisatieblokkering. Definitieve verwijdering is uitsluitend mogelijk voor ongebruikte, gewone accounts zonder uren, planning of beveiligingshistoriek. Eigenaar- en platformbeheerderaccounts blijven beschermd.

### Instellingen voor uitnodigingen en e-mailherstel

Voeg aan **Streamlit → Settings → Secrets** de publieke basis-URL van jouw eigen app toe (zonder queryparameters of fragment):

```toml
APP_BASE_URL = "https://jouw-eigen-app.streamlit.app"
```

Dit bevat geen credential. Maak geen link op basis van een onbetrouwbare browserheader. Uitnodigingen kunnen daarna direct handmatig gedeeld worden. Tokens worden in de tokentabel alleen gehasht opgeslagen. De beveiligde notificatiewachtrij bevat de uitgaande links om ze te kunnen mailen; beperk toegang tot de database en log deze berichten nooit.

**Echte e-mailverzending is niet automatisch actief.** Configureer en test eerst de SMTP-worker zoals hierboven beschreven. Deze worker draait op een aparte vertrouwde host of geplande job met dezelfde database. Streamlit Community Cloud voert geen achtergrondcron voor deze app uit. Stel pas nadat de worker aantoonbaar verzendt bij Streamlit in:

```toml
EMAIL_DELIVERY_ENABLED = "1"
```

Laat deze vlag weg zolang de worker niet werkt. SMTP-credentials horen alleen bij de verzendworker, niet in gedeelde links, code of chat. Automatische herstelmail is niet live gevalideerd zonder die configuratie. Een ingelogde gebruiker kan het wachtwoord wijzigen zonder SMTP.

### Shiftplanning

**Planning** toont een dag-, week- of maandoverzicht. Medewerkers zien uitsluitend hun eigen diensten. Beheerders zien en beheren het team van hun vestiging, kunnen nieuwe diensten maken, bestaande diensten wijzigen of met een reden annuleren. Een dienst met gekoppelde tijdregistratie kan niet meer verplaatst of geannuleerd worden. Overlappende planning voor dezelfde medewerker wordt over alle vestigingen heen geweigerd, ook bij gelijktijdige aanvragen. Dit controleert geplande diensten, geen wettelijke arbeids- of rusttijden.

Bij **In- en uitklokken → Inklokken voor** kan een medewerker expliciet de geplande shift kiezen. Alleen diens eigen, actieve planning in de gekozen vestiging is toegestaan. Eén geplande shift kan aan één registratie gekoppeld worden; opnieuw inklokken voor dezelfde planning wordt geweigerd. Zonder geplande shift inklokken blijft beschikbaar. Het koppelen stelt geen verplichte starttijd in en stopt de klok niet automatisch. Het planningsoverzicht vergelijkt gekoppelde geregistreerde uren met geplande uren. Die geregistreerde uren kunnen nog op controle wachten; planning vervangt geen shiftgoedkeuring.

### Meldingen bij vergeten uitklokken

**Meldingen** berekent waarschuwingen bij openen of verversen:

- Een actieve registratie meer dan 15 minuten na de eindtijd van de gekoppelde planning.
- Anders een actieve registratie van meer dan 12 uur.
- Voor beheerders: afgesloten diensten die op controle wachten.

Medewerkers zien alleen hun eigen uitklokwaarschuwingen; beheerders zien hun vestiging. Gebruik **Meldingen verversen** om opnieuw te berekenen. Er zijn geen pushnotificaties, achtergrondherinneringen of automatische uitklokacties. Deze signalen vereisen beoordeling van de werkelijke tijden. Geplande of geregistreerde uren worden niet vanzelf definitief goedgekeurd.

## Eenvoudiger gebruikersbeheer

Platformdashboard → Gebruikers toont zoekbare accountkaarten met naam, e-mailadres, status en een knop **Beheren**. Er is geen vooraf geselecteerd account. Je eigen account en andere beschermde accounts tonen vooraf waarom ze niet gewijzigd mogen worden, zonder onbruikbare actieknoppen.

Na Beheren staat de gekozen persoon duidelijk boven de acties. Deactiveren/heractiveren heeft één actieknop en een auditreden. Voor definitief verwijderen van een ongebruikt gewoon account is een afzonderlijke bevestiging vereist. De server controleert opnieuw de rechten en aanwezigheid van gegevens in dezelfde transactie. Registraties, planning, eigendom en beveiligings-/beoordelingshistoriek blokkeren fysieke verwijdering. Verwijderen ruimt alleen het ongebruikte account, de sessies en eventuele losse vestigingskoppelingen op en bewaart een auditgebeurtenis bij de beheerder. Er worden geen uren, organisaties of auditlogs verwijderd.

## Taalkeuze: Nederlands, Frans, Engels, Duits en Spaans

Bovenaan de app staat **Taal / Language**, met Nederlands, Français, English, Deutsch en Español. Ook vóór inloggen kan de taal worden gekozen. Na inloggen wordt de bij het account bewaarde voorkeur geladen. Een wijziging terwijl je bent ingelogd wordt server-side bij dat eigen account opgeslagen en blijft na opnieuw inloggen behouden. Nieuwe registraties gebruiken de taal die op het registratieformulier gekozen was. Bestaande accounts starten bij migratie 0005 op Nederlands.

Menu's, tabbladen, formulieren, toelichtingen, statuslabels, meldingen, validatiefouten en tabelkoppen gebruiken lokale vertaalcatalogi. Persoonlijke namen, bedrijfsnamen, e-mailadressen, adressen en vrije opmerkingen worden niet automatisch vertaald. De app stuurt geen gebruikersgegevens naar een externe vertaalservice. Interne rol- en statuscodes blijven gelijk; taal wijzigt nooit de autorisatie of de betekenis van een goedkeuringsactie.

De vertaalcatalogus staat in `workforce/translations.json`; `workforce/i18n.py` verzorgt vertaling en gecontroleerde invulling van waarden. Tests controleren catalogusdekking, overeenkomende placeholders, de vijf inlogschermen, vertaalde foutmeldingen, taalvoorkeur per gebruiker, persoonlijke gegevens en het goedkeuren van aanvragen in de vier extra talen.

De taalkeuze geldt voor de eigen ShiftFlow-interface. Externe Streamlit/Neon-beheerpagina's en browsermenu's hebben hun eigen taalinstellingen. Auditactiecodes, de huidige uitgaande e-mailtemplates en documentatie blijven ongewijzigd; er wordt geen vrije tekst vertaald. De datum-/tijdnotatie in registratieoverzichten blijft dag-maand-jaar in de ingestelde vestigingstijdzone. Gebruik de ingebouwde taalkeuze; automatische browservertaling kan de gekozen appteksten opnieuw veranderen.

### Vestigingen eenvoudig verwijderen

Ga als platformbeheerder naar **Platformdashboard → Vestigingen beheren**.
Zoek de vestiging, klik **Verwijderen** en bevestig met **Ja, vestiging verwijderen**.
De vestiging verdwijnt direct uit aanvragen en actieve vestigingslijsten; de server weigert ook bestaande sessies toegang tot die vestiging. Actieve shiften worden afgesloten en blijven wachten op controle.
Organisatie, accounts, rollen, planning, uren en auditgegevens blijven bewaard als archief.
Via **Verwijderde vestigingen tonen → Herstellen** kun je een vergissing herstellen; eerdere rollen en goedkeuringsstatus gelden dan opnieuw.
Dit verwijdert geen volledige organisatie en heeft geen effect op andere vestigingen.
Migratie `0006` voegt de archiefdatum en verantwoordelijke toe en wordt bij Community Cloud automatisch uitgevoerd.

## Duidelijk beginscherm voor vestigingsbeheerders

Organisatie-eigenaars en vestigingsadmins openen hun vestiging voortaan op **Overzicht**.
Zes actiekaarten brengen hen direct naar **Medewerkers toevoegen**, **Planning**,
**Medewerkers & rechten**, **Werkuren**, **Shiften controleren** en **Meldingen**.
Het overzicht toont actieve teamleden, ingeklokte medewerkers en nog te controleren shiften.
**Medewerkers toevoegen** opent meteen het uitnodigingsformulier; bestaande accounts koppel je via **Medewerkers & rechten**.
De zijbalk houdt de navigatie zichtbaar. De gekozen pagina wordt per vestiging onthouden.
Voor beheerders die ook een vestigingslidmaatschap hebben, staat eigen tijdregistratie apart onder **Mijn werktijd**.
Inklokken is nooit nodig om beheerfuncties te gebruiken. Medewerkers behouden hun eigen inklokscherm, shiften, planning en meldingen; de bestaande servercontroles blijven gelden.

## Leesbaar auditlog

**Vestigingsbeheer → Auditlog** toont automatisch de laatste 100 gebeurtenissen,
met de meest recente bovenaan. Het overzicht bevat **Datum en tijd**, **Uitgevoerd door**,
**Gebeurtenis**, **Betreft** en **Toelichting**. Tijden gebruiken `APP_TIMEZONE`
(standaard Europe/Brussels), inclusief zomer- en wintertijd.
Goedkeuringen tonen de statuswijziging; rechtenwijzigingen tonen de toegekende rol.
Bij uurcorrecties blijven de oorspronkelijke en gewijzigde tijden en de reden zichtbaar.
Namen en vrije redenen worden niet vertaald; de interface en gebeurtenislabels ondersteunen alle vijf talen.
De ruwe gebeurteniscodes, gebruikersnummers en oorspronkelijke details staan apart onder
**Technische gegevens (voor ondersteuning)**. De opgeslagen auditgegevens worden niet gewijzigd.
Toegang blijft beperkt tot bevoegde beheerders van de betreffende vestiging.
