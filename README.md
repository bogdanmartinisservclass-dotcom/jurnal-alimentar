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

- Sus: navigare intre luni (< si >) si numele lunii curente.
- Grila calendarului: zilele cu notite deja introduse apar colorate
  verde; ziua selectata apare albastra; ziua de azi are cifra rosie.
- Atingi o zi -> jos apar cele trei casete editabile (Mic dejun,
  Pranz, Cina) cu ce e deja salvat pentru ziua respectiva (sau goale).
- Butonul **Salveaza** scrie/actualizeaza notitele zilei selectate.
- Butonul **Sterge** goleste complet notitele zilei selectate.
- Mai jos apar, needitabil, notitele de acum 1 zi si acum 2 zile fata
  de ziua selectata (daca exista).

## Modificari usor de facut ulterior

- Culorile calendarului: constantele `CULOARE_*` la inceputul
  fisierului `main.py`.
- Numarul de zile anterioare afisate jos: in prezent 2 (`zi_minus_1`,
  `zi_minus_2`) in metoda `selecteaza_ziua`.
- Iconita aplicatiei: adauga un fisier `icon.png` (512x512) in folder
  si seteaza `icon.filename = icon.png` in `buildozer.spec`.
