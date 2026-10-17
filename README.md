# Jonas Matte

Jonas Matte er et matematikk- og hukommelsesspill laget med Python og Tkinter.

## Starte programmet

På Windows dobbeltklikker du på `JonasMatte.exe`. Du trenger ikke å åpne Visual Studio Code eller installere Python for å kjøre den ferdigbygde `.exe`-filen.

Hvis du bare vil kjøre programmet, er `.exe`-filen nok. De andre filene er med for å gjøre kildekoden, lisensen og innstillingene tilgjengelige, og for at du enkelt skal kunne bytte bakgrunnsbilde (PS. Bakgrunnsbildet må være 400 px bred og 800 px høy).

Gjeldende versjonsnummer vises nederst på siden for innstillinger og nyheter. Denne utgaven er versjon 1.

## Hva filene gjør

- `JonasMatte.exe` er en ferdigbygget versjon av programmet. Den inneholder Python-koden slik den var da `.exe`-filen ble bygget.
- `main_gui.py` er den åpne, lesbare Python-kildekoden. `.exe`-filen leser ikke denne filen ved oppstart.
- `config.ini` inneholder oppstartsinnstillinger som kan endres uten å bygge `.exe`-filen på nytt. Hvis filen mangler, brukes standardinnstillingene.
- `bg.png` er bakgrunnsbildet. Programmet bruker denne eksterne filen hvis den finnes. En reservekopi av bildet ligger også inne i `.exe`-filen.
- `LISENS.txt` beskriver lisensvilkårene for programvaren.

## Endre innstillinger

Åpne `config.ini` i en teksteditor, for eksempel Notisblokk. Standardinnstillingene er:

```ini
[app]
auto_login_jonas = false
jonas_user_id = 426030
```

`auto_login_jonas` bestemmer om programmet skal forsøke automatisk innlogging på Jonas-kontoen. Standardverdien `false` viser vanlig innlogging. `jonas_user_id` angir bruker-ID-en som brukes dersom automatisk innlogging aktiveres.

Lagre filen og start programmet på nytt for at endringene skal tre i kraft. Bruk `true` eller `false` for automatisk innlogging.

## Kildekode og oppdateringer

Endringer i `main_gui.py` oppdaterer ikke `JonasMatte.exe` automatisk. For at endringer i kildekoden skal bli med i `.exe`-programmet, må det bygges på nytt. Innstillinger i `config.ini` og et nytt `bg.png` kan derimot brukes uten å bygge på nytt.

Kildekoden kan leses og redigeres direkte som vanlig tekst. Python og nødvendige byggeverktøy kreves for å kjøre kildekoden direkte eller bygge en ny `.exe`.

## Brukerdata

Programmet lagrer brukerdata og nyhetsoppdateringer i `users.jsonl` og `news.jsonl` i samme mappe som programmet. Filene opprettes ved behov. Hvis du flytter programmet til en ny mappe eller bare kopierer `.exe`-filen, følger eksisterende kontoer og nyheter ikke automatisk med.

`users.jsonl` kan inneholde brukernavn, passorddata og innloggingstokener. Ikke del denne filen offentlig. Ta en sikkerhetskopi før du flytter eller sletter den.

## Aktivitetslogg

Programmet lagrer en lokal aktivitetslogg i `Logs/activity.jsonl`. Loggen har UTC-tidsstempel og en tilfeldig økt-ID og registrerer blant annet appstart og avslutning, innlogging og utlogging, knappetrykk, spillresultater, endringer av brukernavn/passord, bakgrunnsoppgaver og lesing/skriving av bruker- og nyhetsdata.

JSONL-lesing og -skriving logges som lokal lagringsaktivitet (`local_jsonl`), ikke som ekte nettverks- eller API-kontakt. Programmet sender ikke aktivitetsloggen til en server. Passord, innloggingstokener, innskrevne svar, nyhetstekst og andre feltverdier logges ikke. For spillsvar registreres bare runden og om svaret var riktig.

Loggene roteres automatisk når en fil blir omtrent 5 MB. Programmet beholder den aktive loggen og opptil tre eldre loggfiler i `Logs`. Loggene kan likevel inneholde informasjon om hvordan programmet brukes, så ikke del dem offentlig. Du kan slette loggfilene mens programmet er lukket hvis du vil fjerne den lokale historikken.

## Lisens

Se `LISENS.txt` for lisensvilkårene.
