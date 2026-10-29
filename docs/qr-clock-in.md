# ShiftFlow — QR-inklokstation (proefimplementatie)

De code in `workforce/qr_clock.py` biedt HMAC-ondertekende, persoonsgebonden QR-tokens die elke 15 seconden wisselen. Validatie accepteert het huidige en vorige venster om enige scanvertraging toe te laten.

## Veiligheidsgrens
**Een QR-code is geen bewijs van fysieke aanwezigheid.** Een screenshot kan binnen de korte geldigheid worden doorgegeven. Een in de winkel geïnstalleerde, beheerde scanner moet daarom de scan verwerken. De server hoort pas een inklokactie toe te staan nadat de scanner zich afzonderlijk heeft geauthenticeerd.

## Volgende integratiestappen
1. Maak een beheerde scannerregistratie per vestiging (liefst unieke sleutel per toestel, herstel/intrekking mogelijk).
2. Laat de scanner zich authenticeren tegen een server-endpoint; stel **geen** scannersleutel beschikbaar in een browser of publieke app.
3. Toon de persoonlijke code in een aparte werknemersweergave (bijv. elke 15 seconden vernieuwen).
4. Laat het scan-endpoint de QR server-side valideren, de werknemer/vestiging controleren en de juiste ingeplande shift bepalen.
5. Hergebruik de bestaande `Service.clock_in`-voorwaarden (shiftvenster, afwezigheid, dubbele sessies). Zorg dat de gewone 'Inklokken'-knop vervalt zodra QR-inchecken actief is.
6. Bescherm tegen replay met een atomair verbruikregister (tokenvenster + gebruiker + vestiging), verwerk rate limiting en auditlogs.
7. **Uitklokken blijft de bestaande knop**, zonder QR-code.
8. Voeg migraties, unit/integratietests en een optionele feature flag toe vóór een pilot.

## Configuratie voor lokale tests
`SHIFTFLOW_QR_SECRET`: willekeurige server-side secret van minimaal 32 tekens.

`SHIFTFLOW_SCANNER_KEY`: voor de voorbereidende standalone-verificatie van een scannersleutel; deze voorlopige globale sleutel is niet geschikt als uiteindelijke multi-store toestelregistratie.

Sla secrets uitsluitend buiten GitHub op.
