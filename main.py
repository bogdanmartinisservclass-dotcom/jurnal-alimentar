# -*- coding: utf-8 -*-
"""
Jurnal Alimentar - aplicatie Kivy pentru Android.

Calendar in care, pentru fiecare zi, se pot adauga intrari cu ora,
tip (mancare / bautura) si continut. Intrarile apar cronologic,
pot fi atinse pentru editare/stergere. Bauturile se aleg dintr-o
lista predefinita, editabila din aplicatie. Intrarile de mancare
pot avea optional o poza atasata, aleasa din galerie.

Un ecran de rezumat arata saptamana calendaristica curenta (Luni-
Duminica), cu toate intrarile fiecarei zile si frecventa bauturilor
consumate in acea saptamana.

Datele sunt salvate local intr-o baza de date SQLite, in directorul
privat al aplicatiei (App.user_data_dir), deci raman pe telefon
intre lansari. Pozele sunt copiate in acelasi director privat.
"""

import calendar
import os
import shutil
import sqlite3
import uuid
from collections import Counter
from datetime import date, timedelta

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

LUNI_RO = [
    "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
    "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
]
ZILE_RO = ["Lu", "Ma", "Mi", "Jo", "Vi", "Sa", "Du"]
ZILE_RO_LUNGI = [
    "Luni", "Marti", "Miercuri", "Joi", "Vineri", "Sambata", "Duminica",
]

CULOARE_FUNDAL = (0.97, 0.97, 0.95, 1)
CULOARE_TEXT = (0.12, 0.12, 0.12, 1)
CULOARE_ZI_NORMALA = (0.85, 0.85, 0.85, 1)
CULOARE_ZI_CU_DATE = (0.55, 0.78, 0.55, 1)
CULOARE_ZI_SELECTATA = (0.30, 0.55, 0.85, 1)

CULOARE_MANCARE = (0.35, 0.65, 0.35, 1)
CULOARE_BAUTURA = (0.30, 0.50, 0.75, 1)

BAUTURI_INITIALE = ["Apa", "Cafea", "Ceai", "Lapte", "Suc", "Limonada"]

ORE = ["%02d" % h for h in range(24)]
MINUTE = ["00", "15", "30", "45"]

LUNGIME_TRUNCHIERE = 34


def data_azi():
    return date.today()


def trunchiaza(text, lungime=LUNGIME_TRUNCHIERE):
    text = text or ""
    if len(text) <= lungime:
        return text
    return text[:lungime].rstrip() + "..."


def inceput_saptamana(zi_obj):
    """Returneaza data de Luni a saptamanii calendaristice care contine zi_obj."""
    return zi_obj - timedelta(days=zi_obj.weekday())


def copiaza_poza_in_stocare(cale_sursa, folder_poze):
    """Copiaza o poza selectata in stocarea privata a aplicatiei si returneaza calea noua."""
    os.makedirs(folder_poze, exist_ok=True)
    extensie = os.path.splitext(cale_sursa)[1].lower()
    if not extensie or len(extensie) > 5:
        extensie = ".jpg"
    nume_nou = uuid.uuid4().hex + extensie
    cale_noua = os.path.join(folder_poze, nume_nou)

    if cale_sursa.startswith("content://"):
        _copiaza_din_content_uri(cale_sursa, cale_noua)
    else:
        shutil.copyfile(cale_sursa, cale_noua)
    return cale_noua


def _copiaza_din_content_uri(uri_str, cale_destinatie):
    """Pe Android, poza aleasa din galerie vine ca un content:// URI, nu ca o
    cale de fisier obisnuita. Deschidem un descriptor de fisier prin
    ContentResolver-ul Android si il citim ca pe un fisier normal."""
    from jnius import autoclass

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Uri = autoclass("android.net.Uri")
    activity = PythonActivity.mActivity
    resolver = activity.getContentResolver()
    uri = Uri.parse(uri_str)

    descriptor_parcel = resolver.openFileDescriptor(uri, "r")
    descriptor_brut = descriptor_parcel.getFd()
    descriptor_python = os.dup(descriptor_brut)
    descriptor_parcel.close()

    with os.fdopen(descriptor_python, "rb") as f_in:
        with open(cale_destinatie, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)


class BazaDeDate:
    """Strat peste SQLite: intrari (mancare/bautura) si lista de bauturi."""

    def __init__(self, cale_fisier):
        self.conn = sqlite3.connect(cale_fisier)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS intrari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zi TEXT NOT NULL,
                ora TEXT NOT NULL,
                tip TEXT NOT NULL,
                continut TEXT NOT NULL,
                poza_cale TEXT
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bauturi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nume TEXT UNIQUE NOT NULL
            )
            """
        )
        self.conn.commit()

        # migrare defensiva: daca baza de date exista deja dintr-o
        # versiune anterioara (fara coloana poza_cale), o adaugam acum
        try:
            self.conn.execute("ALTER TABLE intrari ADD COLUMN poza_cale TEXT")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # coloana exista deja

        cur = self.conn.execute("SELECT COUNT(*) FROM bauturi")
        if cur.fetchone()[0] == 0:
            for nume in BAUTURI_INITIALE:
                self.conn.execute(
                    "INSERT OR IGNORE INTO bauturi (nume) VALUES (?)", (nume,)
                )
            self.conn.commit()

    # ---------- intrari ----------

    def intrari_pentru_zi(self, zi_str):
        cur = self.conn.execute(
            "SELECT id, ora, tip, continut, poza_cale FROM intrari "
            "WHERE zi = ? ORDER BY ora ASC, id ASC",
            (zi_str,),
        )
        return [
            {"id": r[0], "ora": r[1], "tip": r[2], "continut": r[3], "poza_cale": r[4]}
            for r in cur.fetchall()
        ]

    def intrari_in_interval(self, zi_start_str, zi_sfarsit_str):
        cur = self.conn.execute(
            "SELECT id, zi, ora, tip, continut, poza_cale FROM intrari "
            "WHERE zi >= ? AND zi <= ? ORDER BY zi ASC, ora ASC, id ASC",
            (zi_start_str, zi_sfarsit_str),
        )
        return [
            {"id": r[0], "zi": r[1], "ora": r[2], "tip": r[3], "continut": r[4], "poza_cale": r[5]}
            for r in cur.fetchall()
        ]

    def adauga_intrare(self, zi_str, ora, tip, continut, poza_cale=None):
        self.conn.execute(
            "INSERT INTO intrari (zi, ora, tip, continut, poza_cale) VALUES (?, ?, ?, ?, ?)",
            (zi_str, ora, tip, continut, poza_cale),
        )
        self.conn.commit()

    def actualizeaza_intrare(self, id_intrare, ora, tip, continut, poza_cale=None):
        self.conn.execute(
            "UPDATE intrari SET ora = ?, tip = ?, continut = ?, poza_cale = ? WHERE id = ?",
            (ora, tip, continut, poza_cale, id_intrare),
        )
        self.conn.commit()

    def sterge_intrare(self, id_intrare):
        self.conn.execute("DELETE FROM intrari WHERE id = ?", (id_intrare,))
        self.conn.commit()

    def zile_cu_date_in_luna(self, an, luna):
        prefix = "%04d-%02d-" % (an, luna)
        cur = self.conn.execute(
            "SELECT DISTINCT zi FROM intrari WHERE zi LIKE ?", (prefix + "%",)
        )
        return {r[0] for r in cur.fetchall()}

    # ---------- bauturi ----------

    def bauturi_lista(self):
        cur = self.conn.execute("SELECT nume FROM bauturi ORDER BY nume ASC")
        return [r[0] for r in cur.fetchall()]

    def adauga_bautura(self, nume):
        nume = nume.strip()
        if not nume:
            return
        self.conn.execute("INSERT OR IGNORE INTO bauturi (nume) VALUES (?)", (nume,))
        self.conn.commit()

    def sterge_bautura(self, nume):
        self.conn.execute("DELETE FROM bauturi WHERE nume = ?", (nume,))
        self.conn.commit()


# ================= widget-uri reutilizabile =================


class FundalColorat(BoxLayout):
    """BoxLayout cu fundal desenat manual, intr-o culoare data."""

    def __init__(self, culoare, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._culoare = Color(*culoare)
            self._dreptunghi = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._actualizeaza, size=self._actualizeaza)

    def _actualizeaza(self, *_a):
        self._dreptunghi.pos = self.pos
        self._dreptunghi.size = self.size

    def seteaza_culoare(self, culoare):
        self._culoare.rgba = culoare


class ButonZi(Button):
    """Buton pentru o zi din grila calendarului, cu fundal colorat manual."""

    def __init__(self, text_zi, culoare, **kwargs):
        super().__init__(text=text_zi, **kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = CULOARE_TEXT
        with self.canvas.before:
            self._culoare = Color(*culoare)
            self._dreptunghi = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._actualizeaza, size=self._actualizeaza)

    def _actualizeaza(self, *_a):
        self._dreptunghi.pos = self.pos
        self._dreptunghi.size = self.size


class PatratColorat(Widget):
    """Un mic patrat colorat (indicator de tip: mancare / bautura)."""

    CULORI = {"mancare": CULOARE_MANCARE, "bautura": CULOARE_BAUTURA}

    def __init__(self, tip, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(14), dp(14)))
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*self.CULORI.get(tip, (0.6, 0.6, 0.6, 1)))
            self._dreptunghi = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._actualizeaza, size=self._actualizeaza)

    def _actualizeaza(self, *_a):
        self._dreptunghi.pos = self.pos
        self._dreptunghi.size = self.size


class RandIntrare(ButtonBehavior, BoxLayout):
    """O linie dintr-o zi: ora + patrat colorat + (poza) + continut trunchiat."""

    def __init__(self, intrare, on_tap=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(34),
                          spacing=dp(8), padding=(dp(4), 0), **kwargs)
        self.intrare = intrare
        if on_tap is not None:
            self.bind(on_release=lambda *_: on_tap(intrare))

        eticheta_ora = Label(
            text=intrare["ora"], size_hint_x=None, width=dp(52), bold=True,
            color=CULOARE_TEXT, halign="left", valign="middle",
        )
        eticheta_ora.bind(size=lambda w, *_: setattr(w, "text_size", w.size))

        patrat = PatratColorat(intrare["tip"])
        patrat_container = AnchorLayout(size_hint_x=None, width=dp(20),
                                         anchor_x="center", anchor_y="center")
        patrat_container.add_widget(patrat)

        self.add_widget(eticheta_ora)
        self.add_widget(patrat_container)

        if intrare.get("poza_cale") and os.path.exists(intrare["poza_cale"]):
            miniatura = Image(source=intrare["poza_cale"], size_hint=(None, None),
                               size=(dp(26), dp(26)), allow_stretch=True, keep_ratio=True)
            self.add_widget(miniatura)

        eticheta_continut = Label(
            text=trunchiaza(intrare["continut"]),
            color=CULOARE_TEXT, halign="left", valign="middle",
        )
        eticheta_continut.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.add_widget(eticheta_continut)


class ListaIntrariZi(BoxLayout):
    """Container vertical cu toate liniile (RandIntrare) unei zile."""

    def __init__(self, editabil=True, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, spacing=dp(2), **kwargs)
        self.editabil = editabil
        self.bind(minimum_height=self.setter("height"))

    def actualizeaza(self, intrari, on_tap=None):
        self.clear_widgets()
        if not intrari:
            gol = Label(
                text="(fara notite)", size_hint_y=None, height=dp(26),
                color=(0.45, 0.45, 0.45, 1), halign="left", valign="middle",
            )
            gol.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
            self.add_widget(gol)
            return
        for intrare in intrari:
            rand = RandIntrare(intrare, on_tap=on_tap if self.editabil else None)
            self.add_widget(rand)


# ================= popup-uri =================


class PopupIntrare(Popup):
    """Popup pentru adaugarea/editarea unei intrari (mancare sau bautura)."""

    def __init__(self, tip, bauturi_disponibile, intrare_existenta, folder_poze,
                 on_salveaza, on_sterge, **kwargs):
        titlu = "Adauga mancare" if tip == "mancare" else "Adauga bautura"
        if intrare_existenta is not None:
            titlu = "Editeaza mancare" if tip == "mancare" else "Editeaza bautura"
        super().__init__(title=titlu, size_hint=(0.9, 0.75 if tip == "mancare" else 0.55), **kwargs)

        self.tip = tip
        self.intrare_existenta = intrare_existenta
        self.folder_poze = folder_poze
        self.on_salveaza = on_salveaza
        self.on_sterge = on_sterge
        self.poza_cale = intrare_existenta["poza_cale"] if intrare_existenta else None
        self.mesaj_eroare_poza = None

        continut = FundalColorat(CULOARE_FUNDAL, orientation="vertical", spacing=dp(10), padding=dp(12))

        # --- ora ---
        rand_ora = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(6))
        rand_ora.add_widget(Label(text="Ora:", size_hint_x=None, width=dp(50), color=CULOARE_TEXT))

        ora_ini, minut_ini = "12", "00"
        if intrare_existenta is not None:
            ora_ini, minut_ini = intrare_existenta["ora"].split(":")

        self.spinner_ora = Spinner(text=ora_ini, values=ORE, size_hint_x=0.5)
        self.spinner_minut = Spinner(text=minut_ini, values=MINUTE, size_hint_x=0.5)
        rand_ora.add_widget(self.spinner_ora)
        rand_ora.add_widget(Label(text=":", size_hint_x=None, width=dp(14), color=CULOARE_TEXT))
        rand_ora.add_widget(self.spinner_minut)
        continut.add_widget(rand_ora)

        # --- continut specific tipului ---
        if tip == "mancare":
            continut.add_widget(Label(text="Ce ai mancat:", size_hint_y=None, height=dp(20),
                                       color=CULOARE_TEXT, halign="left"))
            text_initial = intrare_existenta["continut"] if intrare_existenta else ""
            self.txt_continut = TextInput(text=text_initial, multiline=True, size_hint_y=None, height=dp(70))
            continut.add_widget(self.txt_continut)

            self.zona_poza = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
            self.zona_poza.bind(minimum_height=self.zona_poza.setter("height"))
            continut.add_widget(self.zona_poza)
            self._redeseneaza_zona_poza()
        else:
            continut.add_widget(Label(text="Bautura:", size_hint_y=None, height=dp(20),
                                       color=CULOARE_TEXT, halign="left"))
            valori = bauturi_disponibile if bauturi_disponibile else ["Apa"]
            text_initial = (
                intrare_existenta["continut"]
                if intrare_existenta and intrare_existenta["continut"] in valori
                else valori[0]
            )
            self.spinner_bautura = Spinner(text=text_initial, values=valori)
            continut.add_widget(self.spinner_bautura)

        # --- butoane ---
        rand_butoane = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(46), spacing=dp(8))
        buton_salveaza = Button(text="Salveaza",
                                 background_color=CULOARE_MANCARE if tip == "mancare" else CULOARE_BAUTURA)
        buton_salveaza.bind(on_release=lambda *_: self._salveaza())
        rand_butoane.add_widget(buton_salveaza)

        if intrare_existenta is not None:
            buton_sterge = Button(text="Sterge", background_color=(0.7, 0.3, 0.3, 1))
            buton_sterge.bind(on_release=lambda *_: self._sterge())
            rand_butoane.add_widget(buton_sterge)

        buton_anuleaza = Button(text="Anuleaza")
        buton_anuleaza.bind(on_release=lambda *_: self.dismiss())
        rand_butoane.add_widget(buton_anuleaza)

        continut.add_widget(rand_butoane)
        self.content = continut

    # ---------- poza (doar pentru mancare) ----------

    def _redeseneaza_zona_poza(self):
        self.zona_poza.clear_widgets()

        if self.mesaj_eroare_poza:
            eticheta_eroare = Label(
                text=self.mesaj_eroare_poza, size_hint_y=None, height=dp(22),
                color=(0.75, 0.2, 0.2, 1), halign="left", valign="middle",
            )
            eticheta_eroare.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
            self.zona_poza.add_widget(eticheta_eroare)

        if self.poza_cale and os.path.exists(self.poza_cale):
            previzualizare = Image(source=self.poza_cale, size_hint_y=None, height=dp(120),
                                    allow_stretch=True, keep_ratio=True)
            self.zona_poza.add_widget(previzualizare)

        rand_butoane_poza = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(6))
        text_buton = "Schimba poza" if self.poza_cale else "Alege poza"
        buton_alege = Button(text=text_buton, background_color=(0.5, 0.5, 0.5, 1))
        buton_alege.bind(on_release=lambda *_: self._alege_poza())
        rand_butoane_poza.add_widget(buton_alege)

        if self.poza_cale:
            buton_elimina = Button(text="Elimina poza", background_color=(0.7, 0.3, 0.3, 1))
            buton_elimina.bind(on_release=lambda *_: self._elimina_poza())
            rand_butoane_poza.add_widget(buton_elimina)

        self.zona_poza.add_widget(rand_butoane_poza)

    def _alege_poza(self):
        self.mesaj_eroare_poza = None
        try:
            from plyer import filechooser
            filechooser.open_file(on_selection=self._poza_selectata)
        except Exception:
            self.mesaj_eroare_poza = "Nu s-a putut deschide galeria."
            self._redeseneaza_zona_poza()

    def _poza_selectata(self, selectie):
        if not selectie:
            return
        cale_sursa = selectie[0]
        Clock.schedule_once(lambda *_: self._aplica_poza(cale_sursa), 0)

    def _aplica_poza(self, cale_sursa):
        try:
            self.poza_cale = copiaza_poza_in_stocare(cale_sursa, self.folder_poze)
            self.mesaj_eroare_poza = None
        except Exception:
            self.mesaj_eroare_poza = "Nu s-a putut incarca poza. Incearca din nou."
        self._redeseneaza_zona_poza()

    def _elimina_poza(self):
        self.poza_cale = None
        self._redeseneaza_zona_poza()

    # ---------- salvare / stergere ----------

    def _ora_text(self):
        return "%s:%s" % (self.spinner_ora.text, self.spinner_minut.text)

    def _salveaza(self):
        ora = self._ora_text()
        if self.tip == "mancare":
            continut = self.txt_continut.text.strip()
            if not continut:
                return
            poza_cale = self.poza_cale
        else:
            continut = self.spinner_bautura.text
            poza_cale = None
        id_existent = self.intrare_existenta["id"] if self.intrare_existenta else None
        self.on_salveaza(id_existent, ora, self.tip, continut, poza_cale)
        self.dismiss()

    def _sterge(self):
        self.on_sterge(self.intrare_existenta["id"])
        self.dismiss()


class PopupBauturi(Popup):
    """Popup pentru administrarea listei de bauturi (adaugare/stergere)."""

    def __init__(self, db, on_schimbare, **kwargs):
        super().__init__(title="Lista de bauturi", size_hint=(0.9, 0.7), **kwargs)
        self.db = db
        self.on_schimbare = on_schimbare

        radacina = FundalColorat(CULOARE_FUNDAL, orientation="vertical", spacing=dp(8), padding=dp(12))

        self.scroll = ScrollView(size_hint=(1, 1))
        self.lista = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self.lista.bind(minimum_height=self.lista.setter("height"))
        self.scroll.add_widget(self.lista)
        radacina.add_widget(self.scroll)

        rand_adauga = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(6))
        self.txt_noua = TextInput(hint_text="Bautura noua", multiline=False)
        buton_adauga = Button(text="Adauga", size_hint_x=None, width=dp(90),
                               background_color=(0.3, 0.6, 0.3, 1))
        buton_adauga.bind(on_release=lambda *_: self._adauga())
        rand_adauga.add_widget(self.txt_noua)
        rand_adauga.add_widget(buton_adauga)
        radacina.add_widget(rand_adauga)

        buton_inchide = Button(text="Inchide", size_hint_y=None, height=dp(44))
        buton_inchide.bind(on_release=lambda *_: self.dismiss())
        radacina.add_widget(buton_inchide)

        self.content = radacina
        self._reincarca()

    def _reincarca(self):
        self.lista.clear_widgets()
        for nume in self.db.bauturi_lista():
            rand = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(6))
            eticheta = Label(text=nume, color=CULOARE_TEXT, halign="left", valign="middle")
            eticheta.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
            buton_sterge = Button(text="Sterge", size_hint_x=None, width=dp(80),
                                   background_color=(0.7, 0.3, 0.3, 1))
            buton_sterge.bind(on_release=lambda _inst, n=nume: self._sterge(n))
            rand.add_widget(eticheta)
            rand.add_widget(buton_sterge)
            self.lista.add_widget(rand)

    def _adauga(self):
        nume = self.txt_noua.text.strip()
        if not nume:
            return
        self.db.adauga_bautura(nume)
        self.txt_noua.text = ""
        self._reincarca()
        self.on_schimbare()

    def _sterge(self, nume):
        self.db.sterge_bautura(nume)
        self._reincarca()
        self.on_schimbare()


class PopupRaportSaptamanal(Popup):
    """Popup cu rezumatul saptamanii calendaristice curente si frecventa bauturilor."""

    def __init__(self, db, zi_referinta, **kwargs):
        super().__init__(title="Rezumatul saptamanii", size_hint=(0.95, 0.9), **kwargs)
        self.db = db
        self.zi_referinta = zi_referinta
        self._construieste()

    def _construieste(self):
        radacina = FundalColorat(CULOARE_FUNDAL, orientation="vertical", spacing=dp(8), padding=dp(10))

        luni = inceput_saptamana(self.zi_referinta)
        duminica = luni + timedelta(days=6)

        # --- navigare saptamana ---
        rand_nav = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(6))
        buton_prev = Button(text="< Saptamana trecuta")
        buton_prev.bind(on_release=lambda *_: self._schimba_saptamana(-7))
        eticheta_interval = Label(
            text="%s - %s" % (luni.strftime("%d %b"), duminica.strftime("%d %b %Y")),
            bold=True, color=CULOARE_TEXT,
        )
        buton_next = Button(text="Saptamana viitoare >")
        buton_next.bind(on_release=lambda *_: self._schimba_saptamana(7))
        rand_nav.add_widget(buton_prev)
        rand_nav.add_widget(eticheta_interval)
        rand_nav.add_widget(buton_next)
        radacina.add_widget(rand_nav)

        scroll = ScrollView(size_hint=(1, 1))
        coloana = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10), padding=(0, dp(4)))
        coloana.bind(minimum_height=coloana.setter("height"))

        intrari = self.db.intrari_in_interval(luni.isoformat(), duminica.isoformat())
        intrari_pe_zi = {}
        for intrare in intrari:
            intrari_pe_zi.setdefault(intrare["zi"], []).append(intrare)

        for i in range(7):
            zi_obj = luni + timedelta(days=i)
            zi_str = zi_obj.isoformat()
            coloana.add_widget(Label(
                text="%s, %s" % (ZILE_RO_LUNGI[i], zi_obj.strftime("%d %B")),
                bold=True, size_hint_y=None, height=dp(24), color=CULOARE_TEXT,
                halign="left", valign="middle",
            ))
            lista_zi = ListaIntrariZi(editabil=False)
            lista_zi.actualizeaza(intrari_pe_zi.get(zi_str, []))
            coloana.add_widget(lista_zi)

        # --- frecventa bauturilor ---
        coloana.add_widget(Label(
            text="Bauturi consumate saptamana aceasta", bold=True, size_hint_y=None,
            height=dp(28), color=CULOARE_TEXT, halign="left", valign="middle",
        ))
        contor = Counter(
            intrare["continut"] for intrare in intrari if intrare["tip"] == "bautura"
        )
        if not contor:
            coloana.add_widget(Label(
                text="(nicio bautura notata)", size_hint_y=None, height=dp(24),
                color=(0.45, 0.45, 0.45, 1), halign="left", valign="middle",
            ))
        else:
            for nume, numar in sorted(contor.items(), key=lambda x: (-x[1], x[0])):
                rand = Label(
                    text="%s: %d" % (nume, numar), size_hint_y=None, height=dp(22),
                    color=CULOARE_TEXT, halign="left", valign="middle",
                )
                rand.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
                coloana.add_widget(rand)

        scroll.add_widget(coloana)
        radacina.add_widget(scroll)

        buton_inchide = Button(text="Inchide", size_hint_y=None, height=dp(44))
        buton_inchide.bind(on_release=lambda *_: self.dismiss())
        radacina.add_widget(buton_inchide)

        self.content = radacina

    def _schimba_saptamana(self, delta_zile):
        self.zi_referinta = self.zi_referinta + timedelta(days=delta_zile)
        self._construieste()


# ================= ecranul principal =================


class EcranPrincipal(BoxLayout):
    def __init__(self, baza_de_date, folder_poze, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.db = baza_de_date
        self.folder_poze = folder_poze
        self.an_curent = data_azi().year
        self.luna_curenta = data_azi().month
        self.zi_selectata = data_azi()
        self.butoane_zile = {}

        with self.canvas.before:
            Color(*CULOARE_FUNDAL)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._actualizeaza_bg, size=self._actualizeaza_bg)

        scroll = ScrollView(size_hint=(1, 1))
        coloana = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=dp(8))
        coloana.bind(minimum_height=coloana.setter("height"))

        # --- bara de navigare luna ---
        bara_luna = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(4))
        buton_prev = Button(text="<", size_hint_x=None, width=dp(48))
        buton_prev.bind(on_release=lambda *_: self.schimba_luna(-1))
        self.eticheta_luna = Label(text="", bold=True, font_size="18sp", color=CULOARE_TEXT)
        buton_next = Button(text=">", size_hint_x=None, width=dp(48))
        buton_next.bind(on_release=lambda *_: self.schimba_luna(1))
        bara_luna.add_widget(buton_prev)
        bara_luna.add_widget(self.eticheta_luna)
        bara_luna.add_widget(buton_next)
        coloana.add_widget(bara_luna)

        buton_raport = Button(text="Rezumatul saptamanii", size_hint_y=None, height=dp(40),
                               background_color=(0.55, 0.45, 0.65, 1))
        buton_raport.bind(on_release=lambda *_: self.deschide_raport())
        coloana.add_widget(buton_raport)

        # --- grila calendar ---
        self.container_grila = GridLayout(cols=7, size_hint_y=None, spacing=dp(2))
        self.container_grila.bind(minimum_height=self.container_grila.setter("height"))
        coloana.add_widget(self.container_grila)

        # --- panou ziua selectata ---
        coloana.add_widget(self._separator("Ziua selectata"))
        self.eticheta_zi_selectata = Label(
            text="", bold=True, size_hint_y=None, height=dp(24), color=CULOARE_TEXT,
            halign="left",
        )
        self.eticheta_zi_selectata.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        coloana.add_widget(self.eticheta_zi_selectata)

        self.lista_zi = ListaIntrariZi(editabil=True)
        coloana.add_widget(self.lista_zi)

        rand_adauga = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(8))
        buton_adauga_mancare = Button(text="+ Adauga mancare", background_color=CULOARE_MANCARE)
        buton_adauga_mancare.bind(on_release=lambda *_: self.deschide_adaugare("mancare"))
        buton_adauga_bautura = Button(text="+ Adauga bautura", background_color=CULOARE_BAUTURA)
        buton_adauga_bautura.bind(on_release=lambda *_: self.deschide_adaugare("bautura"))
        rand_adauga.add_widget(buton_adauga_mancare)
        rand_adauga.add_widget(buton_adauga_bautura)
        coloana.add_widget(rand_adauga)

        buton_bauturi = Button(text="Editeaza lista de bauturi", size_hint_y=None, height=dp(38),
                                background_color=(0.5, 0.5, 0.5, 1))
        buton_bauturi.bind(on_release=lambda *_: self.deschide_lista_bauturi())
        coloana.add_widget(buton_bauturi)

        # --- previzualizare zile anterioare ---
        coloana.add_widget(self._separator("Zilele anterioare"))

        self.eticheta_zi_minus_1 = self._eticheta_data_preview()
        self.lista_zi_minus_1 = ListaIntrariZi(editabil=False)
        coloana.add_widget(self.eticheta_zi_minus_1)
        coloana.add_widget(self.lista_zi_minus_1)

        self.eticheta_zi_minus_2 = self._eticheta_data_preview()
        self.lista_zi_minus_2 = ListaIntrariZi(editabil=False)
        coloana.add_widget(self.eticheta_zi_minus_2)
        coloana.add_widget(self.lista_zi_minus_2)

        scroll.add_widget(coloana)
        self.add_widget(scroll)

        self.construieste_grila()
        self.selecteaza_ziua(self.zi_selectata)

    # ---------- widget-uri ajutatoare ----------

    def _actualizeaza_bg(self, *_args):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _separator(self, text):
        return Label(
            text=text, bold=True, size_hint_y=None, height=dp(28),
            color=(0.2, 0.2, 0.2, 1),
        )

    def _eticheta_data_preview(self):
        et = Label(text="", bold=True, size_hint_y=None, height=dp(20),
                    color=(0.3, 0.3, 0.3, 1), halign="left", valign="middle")
        et.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        return et

    # ---------- logica calendar ----------

    def schimba_luna(self, delta):
        luna = self.luna_curenta + delta
        an = self.an_curent
        if luna < 1:
            luna = 12
            an -= 1
        elif luna > 12:
            luna = 1
            an += 1
        self.luna_curenta = luna
        self.an_curent = an
        self.construieste_grila()

    def construieste_grila(self):
        self.container_grila.clear_widgets()
        self.butoane_zile = {}

        self.eticheta_luna.text = "%s %d" % (LUNI_RO[self.luna_curenta - 1], self.an_curent)

        for nume_zi in ZILE_RO:
            self.container_grila.add_widget(
                Label(text=nume_zi, bold=True, size_hint_y=None, height=dp(24),
                      color=(0.3, 0.3, 0.3, 1))
            )

        cal = calendar.Calendar(firstweekday=0)
        zile_cu_date = self.db.zile_cu_date_in_luna(self.an_curent, self.luna_curenta)
        azi = data_azi()
        zile_luna = list(cal.itermonthdates(self.an_curent, self.luna_curenta))

        for zi_obj in zile_luna:
            in_luna_curenta = zi_obj.month == self.luna_curenta
            zi_str = zi_obj.isoformat()

            if not in_luna_curenta:
                buton = ButonZi(str(zi_obj.day), (0, 0, 0, 0), size_hint_y=None, height=dp(40))
                buton.color = (0.7, 0.7, 0.7, 0.6)
                buton.disabled = True
            else:
                if zi_obj == self.zi_selectata:
                    culoare = CULOARE_ZI_SELECTATA
                elif zi_str in zile_cu_date:
                    culoare = CULOARE_ZI_CU_DATE
                else:
                    culoare = CULOARE_ZI_NORMALA
                buton = ButonZi(str(zi_obj.day), culoare, size_hint_y=None, height=dp(40))
                if zi_obj == azi:
                    buton.color = (0.85, 0.15, 0.15, 1)
                    buton.bold = True
                buton.bind(on_release=lambda inst, zo=zi_obj: self.selecteaza_ziua(zo))
                self.butoane_zile[zi_str] = buton

            self.container_grila.add_widget(buton)

        randuri = len(zile_luna) // 7 + 1
        self.container_grila.height = dp(24) + randuri * dp(42)

    def selecteaza_ziua(self, zi_obj):
        self.zi_selectata = zi_obj
        self.eticheta_zi_selectata.text = zi_obj.strftime("%A, %d %B %Y")

        intrari = self.db.intrari_pentru_zi(zi_obj.isoformat())
        self.lista_zi.actualizeaza(intrari, on_tap=self.deschide_editare)

        zi_minus_1 = zi_obj - timedelta(days=1)
        zi_minus_2 = zi_obj - timedelta(days=2)
        self.eticheta_zi_minus_1.text = zi_minus_1.strftime("%d %B %Y")
        self.eticheta_zi_minus_2.text = zi_minus_2.strftime("%d %B %Y")
        self.lista_zi_minus_1.actualizeaza(self.db.intrari_pentru_zi(zi_minus_1.isoformat()))
        self.lista_zi_minus_2.actualizeaza(self.db.intrari_pentru_zi(zi_minus_2.isoformat()))

        if zi_obj.month != self.luna_curenta or zi_obj.year != self.an_curent:
            self.an_curent = zi_obj.year
            self.luna_curenta = zi_obj.month
        self.construieste_grila()

    # ---------- adaugare / editare intrari ----------

    def deschide_adaugare(self, tip):
        popup = PopupIntrare(
            tip=tip,
            bauturi_disponibile=self.db.bauturi_lista(),
            intrare_existenta=None,
            folder_poze=self.folder_poze,
            on_salveaza=self._salveaza_intrare,
            on_sterge=self._sterge_intrare,
        )
        popup.open()

    def deschide_editare(self, intrare):
        popup = PopupIntrare(
            tip=intrare["tip"],
            bauturi_disponibile=self.db.bauturi_lista(),
            intrare_existenta=intrare,
            folder_poze=self.folder_poze,
            on_salveaza=self._salveaza_intrare,
            on_sterge=self._sterge_intrare,
        )
        popup.open()

    def _salveaza_intrare(self, id_existent, ora, tip, continut, poza_cale):
        zi_str = self.zi_selectata.isoformat()
        if id_existent is None:
            self.db.adauga_intrare(zi_str, ora, tip, continut, poza_cale)
        else:
            self.db.actualizeaza_intrare(id_existent, ora, tip, continut, poza_cale)
        self.selecteaza_ziua(self.zi_selectata)

    def _sterge_intrare(self, id_intrare):
        self.db.sterge_intrare(id_intrare)
        self.selecteaza_ziua(self.zi_selectata)

    def deschide_lista_bauturi(self):
        popup = PopupBauturi(self.db, on_schimbare=lambda: self.selecteaza_ziua(self.zi_selectata))
        popup.open()

    def deschide_raport(self):
        popup = PopupRaportSaptamanal(self.db, self.zi_selectata)
        popup.open()


# ================= ecran de bun venit =================


class EcranBunVenit(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        radacina = BoxLayout(orientation="vertical")
        with radacina.canvas.before:
            Color(*CULOARE_FUNDAL)
            self._bg = Rectangle(pos=radacina.pos, size=radacina.size)
        radacina.bind(pos=self._actualizeaza_bg, size=self._actualizeaza_bg)

        mesaj = Label(
            markup=True,
            text="[size=24][color=333333]Pentru tine,[/color][/size]\n[size=36][b][color=C9971F]BUCURIA MEA[/color][/b][/size]",
            halign="center", valign="middle",
        )
        mesaj.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        radacina.add_widget(mesaj)
        self.add_widget(radacina)

    def _actualizeaza_bg(self, widget, *_args):
        self._bg.pos = widget.pos
        self._bg.size = widget.size


# ================= aplicatia =================


class JurnalAlimentarApp(App):
    title = "Jurnal Alimentar"

    def build(self):
        Window.clearcolor = CULOARE_FUNDAL
        cale_db = os.path.join(self.user_data_dir, "jurnal_alimentar.db")
        self.db = BazaDeDate(cale_db)
        folder_poze = os.path.join(self.user_data_dir, "poze")

        sm = ScreenManager(transition=FadeTransition(duration=0.3))

        ecran_bun_venit = EcranBunVenit(name="bun_venit")
        sm.add_widget(ecran_bun_venit)

        ecran_principal = Screen(name="principal")
        ecran_principal.add_widget(EcranPrincipal(self.db, folder_poze))
        sm.add_widget(ecran_principal)

        sm.current = "bun_venit"
        Clock.schedule_once(lambda *_: setattr(sm, "current", "principal"), 2.0)

        return sm


if __name__ == "__main__":
    JurnalAlimentarApp().run()
