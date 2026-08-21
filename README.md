# Jurnal Alimentar (aplicatie Android)

Aplicatie Python (Kivy) — calendar in care poti nota, pentru fiecare zi,
ce s-a mancat la Mic dejun / Pranz / Cina. Datele se salveaza local pe
telefon (SQLite), nu ies din aplicatie.

## Cum obtii fisierul APK (cel mai simplu mod — fara instalare pe PC)

Ai nevoie doar de un cont gratuit de GitHub.

1. Creeaza un repository nou pe https://github.com (de exemplu
   `jurnal-alimentar`), gol, fara README.
2. Incarca in el TOATE fisierele din acest folder, pastrand structura
   (inclusiv folderul ascuns `.github/workflows/build-apk.yml`). Cel mai
   simplu: pe pagina repository-ului apasa "Add file" -> "Upload files"
   si trage toate fisierele/folderele (GitHub pastreaza structura de
   foldere daca tragi folderul intreg, sau poti folosi git din linia de
   comanda daca esti obisnuit).
3. Dupa ce ai incarcat fisierele (commit pe branch-ul `main`), mergi la
   tab-ul **Actions** al repository-ului. Se va porni automat un job
   numit "Build APK" (dureaza aproximativ 10-20 de minute prima data,
   pentru ca descarca Android SDK/NDK).
4. Cand jobul se termina (bulina verde), intra pe el si la sectiunea
   **Artifacts**, din josul paginii, vei gasi `jurnal-alimentar-apk` —
   e un fisier zip care contine APK-ul. Descarca-l pe telefon (sau pe
   PC si il transferi pe telefon).
5. Pe telefonul Android, deschide fisierul `.apk` descarcat. Daca
   telefonul intreaba de "instalare din surse necunoscute", permite
   pentru aplicatia din care il deschizi (Fisiere / Chrome, etc.) — e
   normal pentru un APK care nu vine din Play Store.

## Varianta alternativa — build local (Linux/WSL)

Daca preferi sa construiesti singur, ai nevoie de Linux (sau WSL pe
Windows):

```bash
pip install buildozer cython
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf \
    libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
    libtinfo5 cmake libffi-dev libssl-dev

cd jurnal_alimentar
buildozer android debug
```

APK-ul rezultat apare in `bin/jurnalalimentar-1.0-arm64-v8a_armeabi-v7a-debug.apk`.
Prima rulare dureaza mult (descarca SDK-ul Android si NDK-ul).

## Cum functioneaza aplicatia

- La deschidere apare 2 secunde un mesaj de bun venit, apoi calendarul.
- Sus: navigare intre luni (< si >) si numele lunii curente.
- Grila calendarului: zilele cu intrari deja introduse apar colorate
  verde; ziua selectata apare albastra; ziua de azi are cifra rosie.
- Atingi o zi -> jos apare lista cronologica a intrarilor din ziua
  respectiva (ora + pictograma + continut), sau "(fara notite)" daca
  e goala.
- Butonul **+ Adauga mancare** deschide un popup cu selectarea orei
  (doua liste: ora si minut, din 15 in 15), o caseta de text liber,
  si optional o poza (buton **Alege poza**, care deschide galeria
  telefonului; poza aleasa poate fi eliminata cu **Elimina poza**).
- Butonul **+ Adauga bautura** deschide un popup similar, dar cu
  bautura aleasa dintr-o lista predefinita in loc de text liber, plus
  cantitatea (litri), aleasa tot dintr-o lista predefinita (bauturile
  nu au poza).
- Atingi o linie existenta din lista -> se deschide acelasi tip de
  popup, precompletat, unde poti modifica ora/continutul/poza/
  cantitatea sau apasa **Sterge**.
- Butonul **Editeaza lista de bauturi** deschide un popup unde poti
  adauga bauturi noi sau sterge din cele existente (initial: Apa,
  Cafea, Ceai, Lapte, Suc, Limonada).
- Butonul **Editeaza lista de cantitati** face acelasi lucru pentru
  cantitatile disponibile (initial: 0.25L, 0.5L, 0.75L, 1L, 1.5L,
  2L, 2.5L).
- Mai jos apar, needitabil, listele de intrari de acum 1 zi si acum
  2 zile fata de ziua selectata.
- Butonul **Rezumatul saptamanii** (sus, sub navigarea de luna)
  deschide un popup cu saptamana calendaristica curenta (Luni-
  Duminica): toate intrarile fiecarei zile (cu totalul de lichide al
  fiecarei zile), un rezumat cu de cate ori si cati litri a fost
  consumata fiecare bautura in acea saptamana, si un total general
  de litri pe toata saptamana. Are butoane de navigare (< / >)
  intre saptamani.

## Testare pe calculator (fara telefon)

```bash
pip install kivy plyer
python main.py
```

Se deschide o fereastra cu aplicatia. Poti testa tot, inclusiv
alegerea unei poze (foloseste selectorul de fisiere al sistemului
de operare). Util pentru a vedea rapid o modificare, fara sa mai
astepti build-ul de pe GitHub (15-25 minute).

## Modificari usor de facut ulterior

- Culorile calendarului si textul: constantele `CULOARE_*` la
  inceputul fisierului `main.py`.
- Mesajul de bun venit: textul din clasa `EcranBunVenit`, sau
  durata de afisare (`Clock.schedule_once(..., 2.0)` in `build()`).
- Pasul de minute la selectarea orei: constanta `MINUTE` (in prezent
  din 15 in 15).
- Lista initiala de bauturi: constanta `BAUTURI_INITIALE`.
- Numarul de zile anterioare afisate jos: in prezent 2 (`zi_minus_1`,
  `zi_minus_2`) in metoda `selecteaza_ziua`.
- Iconita aplicatiei: adauga un fisier `icon.png` (512x512) in folder
  si seteaza `icon.filename = icon.png` in `buildozer.spec`.
