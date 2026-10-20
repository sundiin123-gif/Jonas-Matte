# Jonas Matte

Denne readme-en er laget av en KI-modell som har gjenomgått hele koden.
Jonas Matte er et matematikk- og hukommelsesspill laget med Python og Tkinter.

## Starte programmet

På Windows dobbeltklikker du på `JonasMatte.exe`. Første gang oppretter programmet en `JonasMatte`-mappe ved siden av den nedlastede fila, kopierer programmet dit og starter kopien. Standard `config.ini`, denne README-en og `LISENS.txt` legges i mappa hvis de ikke finnes der fra før. Den opprinnelige nedlastede `.exe`-fila blir liggende. Senere starter du appen fra `JonasMatte`-mappa. Du trenger ikke å åpne Visual Studio Code eller installere Python.
Vi anbefaler å sette opp en snarvei til .exe programmet slik at du enkelt kan starte det fra skrivebordet eller oppgavelinjen.

### Filer ved siden av `.exe`-filen

Selve programmet er bygget som én fil. Følgende filer er likevel nyttige eller nødvendige for bestemte funksjoner:

- `JonasMatte.exe` — nødvendig for å starte programmet.
- `config.ini` — legg denne ved siden av `.exe`-filen for å endre brukerinnstillinger.
- `bg.png` — valgfritt. Hvis filen mangler, bruker appen bakgrunnsbildet som er bygget inn i `.exe`-filen. Et eget bilde må være 400 px bredt og 800 px høyt.
- `users.jsonl` — bare nødvendig i lokal modus hvis du vil beholde eksisterende lokale kontoer. Opprettes ved behov.
- `news.jsonl` — bare nødvendig i lokal modus hvis du vil beholde eksisterende lokale nyheter og versjonslogg. Opprettes ved behov.
- `Logs\` — opprettes automatisk når aktivitetsloggen skrives. Ikke nødvendig å kopiere.

Legg appen i en mappe brukeren har skrivetilgang til, siden lokal konto-/nyhetsdata og aktivitetslogger lagres der.

`Jonas_Matte.png`, `Jonas_Matte.ico` og kildekodefiler er ikke nødvendige ved siden av en ferdigbygget `.exe`. PNG/ICO brukes når programmet bygges.

Gjeldende versjonsnummer vises nederst på siden for innstillinger og nyheter. Versjonsloggen åpnes fra knappen rett under Nyheter. Denne utgaven er versjon 1.

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

Endringer i `main_gui.py` oppdaterer ikke `JonasMatte.exe` automatisk. For at endringer i kildekoden skal bli med i `.exe`-programmet, må det bygges på nytt. Innstillinger i `config.ini` og et nytt `bg.png` kan derimot brukes uten å bygge på nytt. Windows-ikonet bygges fra `Jonas_Matte.png` som `Jonas_Matte.ico`; begge ikonfilene må være tilgjengelige i prosjektmappen når du bygger.

Kildekoden kan leses og redigeres direkte som vanlig tekst. Python og nødvendige byggeverktøy kreves for å kjøre kildekoden direkte eller bygge en ny `.exe`.

## Brukerdata

I lokal modus lagrer programmet brukerdata, nyheter og versjonslogginnlegg i `users.jsonl` og `news.jsonl` i samme mappe som programmet. Filene opprettes ved behov. Hvis du flytter programmet til en ny mappe, følger lokale data ikke automatisk med.

`users.jsonl` inneholder brukernavn og passord i lesbar tekst i den lokale utgaven. Ikke del eller last opp filen offentlig. Ta vare på en privat sikkerhetskopi.

## Aktivitetslogg

Programmet lagrer en lokal aktivitetslogg i `Logs/activity.jsonl`. Loggen har UTC-tidsstempel og en tilfeldig økt-ID og registrerer blant annet appstart og avslutning, innlogging og utlogging, knappetrykk, spillresultater, endringer av brukernavn/passord, bakgrunnsoppgaver og lesing/skriving av bruker- og nyhetsdata.

Selve aktivitetsloggen lagres lokalt og sendes ikke til en server. Passord, innloggingstokener, innskrevne svar, nyhetstekst og andre feltverdier logges ikke. For spillsvar registreres bare runden og om svaret var riktig.

Loggene roteres automatisk når en fil blir omtrent 5 MB. Programmet beholder den aktive loggen og opptil tre eldre loggfiler i `Logs`. Loggene kan likevel inneholde informasjon om hvordan programmet brukes, så ikke del dem offentlig. Du kan slette loggfilene mens programmet er lukket hvis du vil fjerne den lokale historikken.

## Lisens

Se `LISENS.txt` for lisensvilkårene.
