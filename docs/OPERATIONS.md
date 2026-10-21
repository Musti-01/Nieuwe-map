# ShiftFlow: e-mail, afwezigheden, medische documenten en back-ups

## Wachtwoordherstel activeren

De loginpagina heeft **Wachtwoord vergeten?**. De app maakt een eenmalige link
die één uur geldig is; na wijzigen vervallen alle bestaande sessies. Er geldt
een maximum van drie aanvragen per e-mailadres per kwartier. Het antwoord
verraadt niet of een account bestaat. Beheerders zien geen wachtwoorden of
herstellinks.

Streamlit Community Cloud kan SMTP beperken. De app ondersteunt daarom Resend
via HTTPS, zonder aparte mailworker. Verifieer eerst je afzenderdomein bij
Resend en zet deze waarden uitsluitend in **Streamlit → App settings → Secrets**:

```toml
APP_BASE_URL = "https://jouw-eigen-app.streamlit.app"
MAIL_FROM = "ShiftFlow <platform@jouw-geverifieerde-domein.example>"
RESEND_API_KEY = "VUL_VEILIG_IN_BIJ_STREAMLIT"
EMAIL_DELIVERY_ENABLED = "1"
SICK_NOTE_RETENTION_DAYS = "30"
```

Gebruik het echte publieke adres zonder queryparameters. API-sleutels horen
niet in Git, chat of documentatie. Een andere host kan de bestaande SMTP-route
met geverifieerde TLS gebruiken; zie `.env.example`. Een ingestelde dienst is
geen bewijs van bezorging: vraag met je eigen account een link aan, controleer
ontvangst en doorloop het volledige herstel. Kijk ook bij **Platformdashboard →
Systeemstatus**. Zolang deze instellingen ontbreken blijft herstel uitgeschakeld.

De app start één achtergrondworker per proces. Die controleert iedere 30
seconden de databasewachtrij; database-locks voorkomen gelijktijdige verzending
van dezelfde rij. De HTTPS-route gebruikt een idempotentiesleutel. Fouten worden
maximaal vijf keer geprobeerd; verlopen herstel- en uitnodigingslinks worden
niet meer verzonden. Na succesvolle verzending wordt de berichttekst gewist.
Streamlit kan slapen: tijdens slaap worden geen berichten bezorgd. Een nieuwe
appsessie start de worker opnieuw. Voor continue verzending kan dezelfde
`python -m workforce.mail` op een eigen geplande worker worden uitgevoerd.

## Ziekte en verlof

Bij **Afwezigheden** meldt een gekoppelde medewerker ziekte of vraagt verlof
aan met een eerste en laatste dag, beide inbegrepen. Ziekte wordt meteen
geregistreerd; verlof blijft in afwachting totdat een bevoegde beheerder het
goedkeurt of weigert. Een beheerder keurt eigen verlof niet zelf goed; een
platformbeheerder kan dit beoordelen. Een medewerker kan een eigen openstaande
verlofaanvraag annuleren. Een beheerder kan een registratie annuleren wanneer
die gecorrigeerd moet worden. Vermeld geen diagnose of andere medische details.

**Planning** toont afwezigheden en conflicten met bestaande shiften. Die shiften
worden niet automatisch verwijderd of als gewerkte uren geboekt. Tijdens
goedgekeurde afwezigheid weigert de server nieuwe overlappende shiften en
inklokken voor die vestiging. Uitklokken blijft mogelijk. Datums gebruiken
`APP_TIMEZONE` en afwezigheden worden per vestiging geregistreerd.

## Ziektebriefjes en bewaartermijn

Een medewerker kan een document koppelen aan een eigen ziekmelding, of tegelijk
met uploaden een nieuwe ziekmelding met datums aanmaken. Alleen
**platformbeheerders, inclusief de platformeigenaar**, mogen het document
downloaden of verwijderen. Organisatie-eigenaars, vestigingsadmins en andere
medewerkers kunnen geen documenten van anderen opvragen. De indiener ziet de
eigen uploadmetadata, zonder downloadknop. Medische documentinhoud staat niet
in de planning, notificaties of foutregistratie.

Verwijderen vraagt expliciete bevestiging. Het verwijdert de documentinhoud
uit de primaire database; afwezigheidsregistratie en auditgeschiedenis blijven.
`SICK_NOTE_RETENTION_DAYS` bepaalt de bewaartermijn voor nieuwe uploads: standaard
30 dagen na de laatste ziektedag of upload, afhankelijk van welke later valt.
Dit is een configureerbare technische standaard, geen wettelijke bewaartermijn.
Stel een passende eigen termijn vast. Een gewijzigde instelling geldt voor
nieuwe uploads; bestaande vervaldatums worden niet stilzwijgend verlengd.

Migratie `0008` geeft bestaande documenten een vervaldatum van 30 dagen na de
oorspronkelijke upload. Verlopen documenten zijn direct niet meer zichtbaar
of downloadbaar. Fysieke opschoning gebeurt bij appstart, periodiek door de
actieve mailworker en dagelijks door de back-uptaak. De opdracht
`python -m workforce.operations` kan ook apart gepland worden.

Streamlit levert een opgevraagd bestand via een tijdelijke download-URL.
Reeds gedownloade kopieën kunnen niet worden teruggeroepen. Een verwijderde
brief kan bovendien nog maximaal zeven dagen in bestaande back-uparchieven
aanwezig zijn. Verwijder verlopen documenten opnieuw na herstel, vóór de app
weer voor gebruikers beschikbaar wordt.

## Dagelijkse versleutelde back-ups activeren

Het bestand `.github/workflows/backups.yml` bevat een dagelijkse taak om
01:15 UTC en kan via **GitHub → Actions → Encrypted database backup → Run
workflow** handmatig gestart worden. De taak ruimt verlopen documenten op,
maakt een PostgreSQL-dump, versleutelt die met GPG/AES256 en slaat uitsluitend
het versleutelde bestand als Actions-artifact op. Bewaring: zeven dagen.

Je gebruikt Neon. Kies in je Neon-project **Connect** de juiste productiebranch
(en niet een tijdelijke previewbranch) en zet **Connection pooling** uit voor
het back-upadres. Gebruik de directe PostgreSQL-URL met de TLS-opties die Neon
opgeeft. De Streamlit-app mag de bestaande gepoolde verbinding blijven gebruiken.
Controleer in Neon bij **Restore / Restore history** hoeveel herstelhistoriek
jouw huidige abonnement biedt en stel de gewenste termijn daar in; de precieze
beschikbaarheid hangt af van het abonnement. Verwijder of reset de productiebranch
niet om een hersteltest uit te voeren.

Stel in **GitHub → Repository settings → Secrets and variables → Actions** in:

- `BACKUP_DATABASE_URL`: de directe database-URL van je productieprovider, met
  de vereiste TLS-opties. Gebruik een geschikte back-upgebruiker met leesrechten
  voor alle tabellen plus rechten voor opschoning en het operationele log.
- `BACKUP_PASSPHRASE`: een unieke willekeurige sleutel van minstens 20 tekens.
  Bewaar een tweede kopie in je wachtwoordmanager. Zonder deze sleutel zijn de
  archieven niet herstelbaar. Bewaar oude sleutels tot hun archieven verlopen.

De taak vereist PostgreSQL 16, 17 of 18; de helper kiest dezelfde clientversie.
Wachtwoorden worden via procesomgeving doorgegeven, niet als commandoregel.
Een tussenbestand zonder versleuteling bestaat alleen in een afgeschermde
tijdelijke map op de taakrunner en wordt na gebruik verwijderd. Geef alleen
vertrouwde beheerders toegang tot de repository en Actions-secrets. Beoordeel
ook of deze opslag past bij de eisen voor jouw persoonsgegevens.

Start na het invullen meteen één handmatige run. Controleer dat hij slaagt en
een `.dump.gpg`-artifact oplevert. **Systeemstatus** toont pas een geslaagde
back-up nadat de opslagstap succesvol terugmeldt. Een ontbrekende back-up of
een laatste back-up ouder dan 26 uur geeft een waarschuwing. Activeer daarnaast
de ingebouwde back-ups en, waar beschikbaar, point-in-time recovery bij je
databaseprovider. Dat provideronderdeel moet in diens eigen console worden
ingesteld; een GitHub-taak schakelt het niet in.

De planning van GitHub Actions kan vertraagd worden en kan op inactieve publieke
repositories worden uitgeschakeld. Controleer meldingen en taakgeschiedenis;
deze taak belooft geen gegarandeerd hersteltijdstip of continue bewaking.

## Herstel testen

Doe dit regelmatig en na schemawijzigingen, op een vertrouwde machine met
Python 3.12, Docker en GPG. Download een artifact via GitHub en pak het uit.
Maak een **nieuwe lege** database die op `_restore_test` eindigt, met dezelfde
PostgreSQL-hoofdversie. Stel `RESTORE_DATABASE_URL` en `BACKUP_PASSPHRASE`
veilig in de procesomgeving in. Voer vervolgens uit:

```bash
cd /pad/naar/Nieuwe-map
.venv/bin/python -m workforce.backup --verify-archive /veilig/pad/shiftflow-backup.dump.gpg
```

De opdracht weigert een andere databasenaam of een niet-lege database,
ontsleutelt het archief, voert `pg_restore --exit-on-error` uit en controleert
de schemaversie en kerngegevens. Controleer vervolgens steekproefsgewijs
gebruikers, uren en documentinhoud en vergelijk met de verwachte back-updatum.
Verwijder de wegwerpdatabase na de test. Voor een echt herstel maak je eerst
een nieuwe productiedatabase, test je die en wijzig je pas daarna de appbinding;
overschrijf nooit blind de bestaande productiegegevens.

Tijdens ontwikkeling is een volledige ronde met synthetische gegevens getest:
dump, versleuteling, weigeren van een verkeerde sleutel, herstel in een andere
database en vergelijking van de exacte documentbytes. Dit bewijst niet dat de
nog in te stellen productieprovider en Actions-secrets al werken.

## Centrale foutregistratie

Verwachte invoer- en rechtenfouten worden gewoon bij het formulier getoond.
Onverwachte fouten krijgen een referentiecode. Het operationele overzicht is
alleen voor platformbeheerders en bewaart maximaal 30 dagen gebeurtenissen.
Wachtwoorden, API-sleutels, herstel-URL's, medische inhoud, SQL-parameters en
ruwe exceptionteksten worden niet daarin opgeslagen. Als de database zelf niet
bereikbaar is, gaat dezelfde beperkte referentie naar de hostinglogs.

Bekijk ook de hostinglogs en stel providerwaarschuwingen in voor beschikbaarheid
en back-upfouten. Het dashboard is een controlepunt, geen externe 24/7-monitor.
