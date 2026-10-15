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

SMTP-verzending heeft nog steeds een geplande worker nodig. Streamlit Community Cloud voert geen periodieke worker voor deze app uit. Besluiten worden wel betrouwbaar in de outbox opgeslagen; voor echte mail moet een aparte vertrouwde worker met dezelfde database- en SMTP-configuratie worden gehost.

Voor klantgebruik blijven backups, privacybeleid en aanvullende authenticatiebescherming nodig zoals beschreven in README. De gratis hostingpakketten kunnen slapen en hebben providerlimieten; dit document belooft geen SLA.

## Nieuwe medewerkers- en planningfuncties activeren

Na de update naar migratie 0004: herstart de app. Bestaande accounts blijven actief en tijdregistraties blijven bewaard. In de vestiging staan Planning en Meldingen; uitnodigingen staan onder Team & rechten en globale accountstatus onder Platformdashboard → Gebruikers.

Voeg voor deelbare uitnodigingslinks `APP_BASE_URL = "https://jouw-eigen-app.streamlit.app"` toe aan Streamlit Secrets. Gebruik het echte publieke app-adres zonder query of fragment. De app toont daarna een link die je zelf aan de medewerker kunt sturen.

Wachtwoordherstel per e-mail vereist eerst een geconfigureerde, werkende externe SMTP-worker. Zet pas na een geslaagde afleveringscontrole `EMAIL_DELIVERY_ENABLED = "1"` in Streamlit Secrets. Zonder die vlag meldt de app eerlijk dat e-mailherstel nog niet beschikbaar is. Het wijzigen van een bekend wachtwoord werkt voor ingelogde gebruikers via het zijmenu, zonder e-mail.

Meldingen over vergeten uitklokken worden in de app berekend wanneer je het scherm opent of ververst. Dit zijn geen achtergrond- of pushmeldingen. Planning vervangt de afzonderlijke urencontrole niet.
