# Online testen met Streamlit Community Cloud

De code op GitHub is nog geen online app. Onderstaande accountstappen voer je in jouw eigen browser uit. Deel geen databasewachtwoorden in chat.

1. Maak een beheerde PostgreSQL-database aan, bijvoorbeeld via Neon. Kies een persistent project; controleer zelf de limieten, slaapstand en eventuele kosten van het gekozen pakket. Kopieer de connection string uit de providerconsole. Een Neon-URL met `sslmode=require` is bruikbaar met de vertrouwde TLS-configuratie van de provider. Schakel certificaatcontrole nooit uit.
2. Open https://share.streamlit.io/ en log in met GitHub. Geef Streamlit toegang tot `Musti-01/Nieuwe-map`.
3. Kies **Create app / Deploy app** en selecteer:
   - Repository: `Musti-01/Nieuwe-map`
   - Branch: `master`
   - Main file path: `cloud_app.py`
   - Python: **3.12** bij de geavanceerde instellingen, indien de interface deze keuze toont.
4. Vul bij **Advanced settings → Secrets** het onderstaande TOML in met jouw echte database-URL. Bewaar dit uitsluitend in de secretinstellingen, niet op GitHub:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require"
APP_TIMEZONE = "Europe/Brussels"
APP_BASE_URL = "https://jouw-eigen-app.streamlit.app"
SHIFTFLOW_QR_SECRET = "EEN_LANGE_WILLEKEURIGE_SECRET_VAN_MINSTENS_32_TEKENS"
```

5. Klik **Deploy**. Streamlit installeert `requirements.txt`. Bij de eerste appstart voert `cloud_app.py` de migraties uit onder een PostgreSQL-lock. Er is geen aparte shell of handmatige schema-installatie nodig. Een databasegebruiker met migratierechten is hiervoor vereist. Starten na slaapstand herhaalt de migratiecontrole veilig.
6. Open de werkelijke `*.streamlit.app` URL die Streamlit aanmaakt. Maak jouw persoonlijke account aan met de organisatiecheckbox uit.
7. Stel jezelf éénmalig als platformeigenaar in via de SQL-editor van jouw databaseprovider. Vervang uitsluitend het e-mailadres hieronder door dat van jouw zojuist geregistreerde persoonlijke account. Dit is een vertrouwde databasebeheeractie, geen openbare appfunctie:

```sql
DO $$
DECLARE account_id integer;
BEGIN
  PERFORM pg_advisory_xact_lock(793125041);
  IF EXISTS (SELECT 1 FROM users WHERE platform_admin = true) THEN
    RAISE EXCEPTION 'Platformbeheerder bestaat al; bootstrap gesloten';
  END IF;
  SELECT id INTO STRICT account_id FROM users
    WHERE email = lower('JOUW-GEREGISTREERDE-EMAIL@EXAMPLE.COM');
  UPDATE users SET platform_owner = true, platform_admin = true
    WHERE id = account_id;
  INSERT INTO audit_events (actor_id, branch_id, action, detail, created_at)
    VALUES (account_id, NULL, 'platform.bootstrap',
            'user=' || account_id::text, CURRENT_TIMESTAMP);
END $$;
```

8. Log opnieuw in. Het **Platformdashboard** is nu zichtbaar. Registreer in een andere browser een testorganisatie, keur eerst organisatie en dan vestiging goed en test de medewerkerflow.

De eenmalige SQL-bootstrap heeft dezelfde lock en beschermingsvoorwaarden als de lokale CLI. Als er al een platformbeheerder is, promoveert hij niemand meer. Bestaande productiegegevens worden door opstarten niet gewist. Migratie 0002 zet oudere organisaties wel verplicht op In afwachting; zie README.

De app ondersteunt Resend via HTTPS voor wachtwoordherstel, uitnodigingen en
besluitmails. Stel `RESEND_API_KEY`, `MAIL_FROM`, `APP_BASE_URL` en
`EMAIL_DELIVERY_ENABLED` veilig in bij Streamlit Secrets. De ingebouwde worker
verzendt uit de wachtrij zolang de app actief is; tijdens slaap staat verzending
stil. Zie [OPERATIONS.md](OPERATIONS.md) voor activering, een echte bezorgtest,
Neon-back-ups en de dagelijkse versleutelde back-upworkflow.

Voor klantgebruik blijven backups, privacybeleid en aanvullende authenticatiebescherming nodig zoals beschreven in README. De gratis hostingpakketten kunnen slapen en hebben providerlimieten; dit document belooft geen SLA.

## Nieuwe medewerkers- en planningfuncties activeren

Na de update naar migratie 0004: herstart de app. Bestaande accounts blijven actief en tijdregistraties blijven bewaard. In de vestiging staan Planning en Meldingen; uitnodigingen staan onder Team & rechten en globale accountstatus onder Platformdashboard → Gebruikers.

Voeg voor deelbare uitnodigingslinks `APP_BASE_URL = "https://jouw-eigen-app.streamlit.app"` toe aan Streamlit Secrets. Gebruik het echte publieke app-adres zonder query of fragment. De app toont daarna een link die je zelf aan de medewerker kunt sturen.

Wachtwoordherstel per e-mail vereist eerst een geconfigureerde, werkende e-maildienst zoals Resend. Zet pas na een geslaagde afleveringscontrole `EMAIL_DELIVERY_ENABLED = "1"` in Streamlit Secrets. Zonder die vlag meldt de app eerlijk dat e-mailherstel nog niet beschikbaar is. Het wijzigen van een bekend wachtwoord werkt voor ingelogde gebruikers via het zijmenu, zonder e-mail.

Meldingen over vergeten uitklokken worden in de app berekend wanneer je het scherm opent of ververst. Dit zijn geen achtergrond- of pushmeldingen. Planning vervangt de afzonderlijke urencontrole niet.


## Beveiligde QR-inklokken en beschikbaarheden

Migratie `0010` voegt winkelscanners, een replay-register voor gebruikte QR-codes en medewerkerbeschikbaarheden toe. `cloud_app.py` voert de migratie bij deployment automatisch uit onder dezelfde migratielock als eerdere schemawijzigingen.

### Winkelscanner koppelen

1. Log in als vestigingsbeheerder en open **Scanners**.
2. Registreer het vaste toestel, bijvoorbeeld **Tablet kassa 1**.
3. ShiftFlow toont één geheime HTTPS-koppellink. Open die link alleen op het bedoelde winkeltoestel en bevestig daarna in de beheerdersinterface dat de koppeling is opgeslagen.
4. Het winkeltoestel kan een vaste USB/Bluetooth QR-scanner gebruiken of de tablet-camera.
5. Trek het toestel onder **Scanners** onmiddellijk in als de koppellink mogelijk is uitgelekt, het toestel wordt vervangen of het niet meer vertrouwd is.

De database bewaart alleen een SHA-256-hash van de scannercredential. De pairingslink zelf is een bearer credential: wie de link bezit kan als die scanner handelen totdat de manager hem intrekt. Gebruik daarom uitsluitend HTTPS en deel de link niet via onbeveiligde kanalen.

### Inklokken als medewerker

De medewerker opent **In- en uitklokken** en toont de persoonlijke QR. Deze QR is gebonden aan medewerker én vestiging en wisselt iedere 15 seconden. De winkelscanner valideert de handtekening en geldigheid server-side, controleert de ingeplande shift en afwezigheden, en claimt de QR atomair als eenmalig gebruikt. Rechtstreeks inklokken vanuit het medewerkeraccount is uitgeschakeld.

Na een succesvolle scan toont de winkelscanner de geregistreerde inkloktijd. Het medewerkeraccount ververst de status en toont dezelfde actieve tijdregistratie. **Uitklokken** blijft de gewone knop in het medewerkeraccount en gebruikt de bestaande urenberekening.

Een doorgestuurde live QR kan tijdens het korte geldigheidsvenster nog door een geautoriseerde scanner worden gescand. De oplossing beperkt dit risico met een korte geldigheid, vestigingsbinding, scannerautorisatie, single-use replaybescherming en auditregistratie, maar levert zonder extra hardware/identiteitscontrole geen absoluut bewijs dat de medewerker fysiek naast de scanner staat.

### Beschikbaarheden

Medewerkers beheren onder **Mijn beschikbaarheid** hun eigen eenmalige of wekelijkse tijdsblokken. Alleen de medewerker zelf kan deze regels wijzigen of verwijderen. Managers zien onder **Beschikbaarheden** een dag-, week- of maandoverzicht en waarschuwingen voor afwezigheden of bestaande shiften.

Bij **Planning** worden medewerkers die het volledige gekozen tijdsblok als beschikbaar hebben opgegeven bovenaan gezet. Een ontbrekende beschikbaarheid is alleen een waarschuwing; het is geen automatische afkeuring of shift. Bestaande serverregels blijven overlappende shiften en goedgekeurde afwezigheden blokkeren.
