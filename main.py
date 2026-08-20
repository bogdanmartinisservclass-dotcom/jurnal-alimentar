# -*- coding: utf-8 -*-
"""
Jurnal Alimentar - aplicatie Kivy pentru Android.
Calendar in care, pentru fiecare zi, se pot introduce/edita/sterge
notite pentru Mic dejun, Pranz si Cina. In partea de jos se afiseaza,
needitabil, ultimele 1-2 zile anterioare zilei selectate.

Datele sunt salvate local intr-o baza de date SQLite, in directorul
privat al aplicatiei (App.user_data_dir), deci raman pe telefon
intre lansari.
"""

import calendar
import os
import sqlite3
from datetime import date, timedelta

from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle

LUNI_RO = [
    "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
    "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
]
ZILE_RO = ["Lu", "Ma", "Mi", "Jo", "Vi", "Sa", "Du"]

CULOARE_FUNDAL = (0.97, 0.97, 0.95, 1)
CULOARE_ZI_NORMALA = (0.85, 0.85, 0.85, 1)
CULOARE_ZI_CU_DATE = (0.55, 0.78, 0.55, 1)
CULOARE_ZI_SELECTATA = (0.30, 0.55, 0.85, 1)
CULOARE_AZI_BORDURA = (0.85, 0.25, 0.25, 1)


def data_azi():
    return date.today()


class BazaDeDate:
    """Strat simplu peste SQLite pentru mesele fiecarei zile."""

    def __init__(self, cale_fisier):
        self.conn = sqlite3.connect(cale_fisier)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mese (
                zi TEXT PRIMARY KEY,
                mic_dejun TEXT,
                pranz TEXT,
                cina TEXT
            )
            """
        )
        self.conn.commit()

    def citeste(self, zi_str):
        cur = self.conn.execute(
            "SELECT mic_dejun, pranz, cina FROM mese WHERE zi = ?", (zi_str,)
        )
        rand = cur.fetchone()
        if rand is None:
            return None
        return {"mic_dejun": rand[0] or "", "pranz": rand[1] or "", "cina": rand[2] or ""}

    def salveaza(self, zi_str, mic_dejun, pranz, cina):
        self.conn.execute(
            """
            INSERT INTO mese (zi, mic_dejun, pranz, cina) VALUES (?, ?, ?, ?)
            ON CONFLICT(zi) DO UPDATE SET
                mic_dejun = excluded.mic_dejun,
                pranz = excluded.pranz,
                cina = excluded.cina
            """,
            (zi_str, mic_dejun, pranz, cina),
        )
        self.conn.commit()

    def sterge(self, zi_str):
        self.conn.execute("DELETE FROM mese WHERE zi = ?", (zi_str,))
        self.conn.commit()

    def zile_cu_date_in_luna(self, an, luna):
        prefix = "%04d-%02d-" % (an, luna)
        cur = self.conn.execute(
            "SELECT zi FROM mese WHERE zi LIKE ?", (prefix + "%",)
        )
        return {rand[0] for rand in cur.fetchall()}


class ButonZi(Button):
    """Buton pentru o zi din grila calendarului, cu fundal colorat manual."""

    def __init__(self, text_zi, culoare, **kwargs):
        super().__init__(text=text_zi, **kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)  # desenam noi fundalul
        self.color = (0, 0, 0, 1)
        with self.canvas.before:
            self._culoare_instr = Color(*culoare)
            self._dreptunghi = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._actualizeaza, size=self._actualizeaza)

    def _actualizeaza(self, *_args):
        self._dreptunghi.pos = self.pos
        self._dreptunghi.size = self.size

    def seteaza_culoare(self, culoare):
        self._culoare_instr.rgba = culoare


class CutiePreview(BoxLayout):
    """Caseta needitabila care arata mesele unei zile anterioare."""

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(2), **kwargs)
        with self.canvas.before:
            Color(0.90, 0.90, 0.88, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._actualizeaza, size=self._actualizeaza)

        self.eticheta_data = Label(
            text="", bold=True, size_hint_y=None, height=dp(20),
            color=(0, 0, 0, 1), halign="left", valign="middle",
        )
        self.eticheta_data.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.eticheta_continut = Label(
            text="", size_hint_y=None, color=(0.15, 0.15, 0.15, 1),
            halign="left", valign="top",
        )
        self.eticheta_continut.bind(
            size=lambda w, *_: setattr(w, "text_size", (w.width, None))
        )
        self.eticheta_continut.bind(texture_size=self._ajusteaza_inaltime)

        self.add_widget(self.eticheta_data)
        self.add_widget(self.eticheta_continut)

    def _actualizeaza(self, *_args):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _ajusteaza_inaltime(self, widget, dimensiune):
        widget.height = dimensiune[1]
        self.height = self.eticheta_data.height + widget.height + dp(6)

    def seteaza_continut(self, zi_obj, date_mese):
        self.eticheta_data.text = zi_obj.strftime("%d %B %Y")
        if date_mese is None:
            self.eticheta_continut.text = "(fara notite)"
            return
        linii = []
        if date_mese["mic_dejun"]:
            linii.append("Mic dejun: " + date_mese["mic_dejun"])
        if date_mese["pranz"]:
            linii.append("Pranz: " + date_mese["pranz"])
        if date_mese["cina"]:
            linii.append("Cina: " + date_mese["cina"])
        self.eticheta_continut.text = "\n".join(linii) if linii else "(fara notite)"


class EcranPrincipal(BoxLayout):
    def __init__(self, baza_de_date, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.db = baza_de_date
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
        self.eticheta_luna = Label(text="", bold=True, font_size="18sp")
        buton_next = Button(text=">", size_hint_x=None, width=dp(48))
        buton_next.bind(on_release=lambda *_: self.schimba_luna(1))
        bara_luna.add_widget(buton_prev)
        bara_luna.add_widget(self.eticheta_luna)
        bara_luna.add_widget(buton_next)
        coloana.add_widget(bara_luna)

        # --- grila calendar ---
        self.container_grila = GridLayout(cols=7, size_hint_y=None, spacing=dp(2))
        self.container_grila.bind(minimum_height=self.container_grila.setter("height"))
        coloana.add_widget(self.container_grila)

        # --- panou ziua selectata ---
        coloana.add_widget(self._separator("Ziua selectata"))
        self.eticheta_zi_selectata = Label(
            text="", bold=True, size_hint_y=None, height=dp(24), color=(0, 0, 0, 1)
        )
        coloana.add_widget(self.eticheta_zi_selectata)

        self.txt_mic_dejun = self._creeaza_textinput()
        self.txt_pranz = self._creeaza_textinput()
        self.txt_cina = self._creeaza_textinput()

        coloana.add_widget(self._eticheta_camp("Mic dejun"))
        coloana.add_widget(self.txt_mic_dejun)
        coloana.add_widget(self._eticheta_camp("Pranz"))
        coloana.add_widget(self.txt_pranz)
        coloana.add_widget(self._eticheta_camp("Cina"))
        coloana.add_widget(self.txt_cina)

        rand_butoane = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(8))
        buton_salveaza = Button(text="Salveaza", background_color=(0.3, 0.6, 0.3, 1))
        buton_salveaza.bind(on_release=lambda *_: self.salveaza_ziua_curenta())
        buton_sterge = Button(text="Sterge", background_color=(0.7, 0.3, 0.3, 1))
        buton_sterge.bind(on_release=lambda *_: self.sterge_ziua_curenta())
        rand_butoane.add_widget(buton_salveaza)
        rand_butoane.add_widget(buton_sterge)
        coloana.add_widget(rand_butoane)

        # --- previzualizare zile anterioare ---
        coloana.add_widget(self._separator("Zilele anterioare"))
        self.cutie_preview_1 = CutiePreview(size_hint_y=None)
        self.cutie_preview_2 = CutiePreview(size_hint_y=None)
        coloana.add_widget(self.cutie_preview_1)
        coloana.add_widget(self.cutie_preview_2)

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

    def _eticheta_camp(self, text):
        return Label(
            text=text, size_hint_y=None, height=dp(18), color=(0.25, 0.25, 0.25, 1),
            halign="left",
        )

    def _creeaza_textinput(self):
        ti = TextInput(
            text="", multiline=True, size_hint_y=None, height=dp(70),
            font_size="15sp",
        )
        return ti

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

        for zi_obj in cal.itermonthdates(self.an_curent, self.luna_curenta):
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

        nr_randuri = self.container_grila.height  # recalculat mai jos
        randuri = len(list(cal.itermonthdates(self.an_curent, self.luna_curenta))) // 7 + 1
        self.container_grila.height = dp(24) + randuri * dp(42)

    def selecteaza_ziua(self, zi_obj):
        self.zi_selectata = zi_obj
        self.eticheta_zi_selectata.text = zi_obj.strftime("%A, %d %B %Y")

        date_zi = self.db.citeste(zi_obj.isoformat())
        self.txt_mic_dejun.text = date_zi["mic_dejun"] if date_zi else ""
        self.txt_pranz.text = date_zi["pranz"] if date_zi else ""
        self.txt_cina.text = date_zi["cina"] if date_zi else ""

        zi_minus_1 = zi_obj - timedelta(days=1)
        zi_minus_2 = zi_obj - timedelta(days=2)
        self.cutie_preview_1.seteaza_continut(zi_minus_1, self.db.citeste(zi_minus_1.isoformat()))
        self.cutie_preview_2.seteaza_continut(zi_minus_2, self.db.citeste(zi_minus_2.isoformat()))

        # daca luna afisata nu contine ziua selectata, mutam calendarul pe ea
        if zi_obj.month != self.luna_curenta or zi_obj.year != self.an_curent:
            self.an_curent = zi_obj.year
            self.luna_curenta = zi_obj.month
        self.construieste_grila()

    def salveaza_ziua_curenta(self):
        self.db.salveaza(
            self.zi_selectata.isoformat(),
            self.txt_mic_dejun.text.strip(),
            self.txt_pranz.text.strip(),
            self.txt_cina.text.strip(),
        )
        self.construieste_grila()
        self._mesaj("Salvat pentru %s" % self.zi_selectata.strftime("%d %B %Y"))

    def sterge_ziua_curenta(self):
        self.db.sterge(self.zi_selectata.isoformat())
        self.txt_mic_dejun.text = ""
        self.txt_pranz.text = ""
        self.txt_cina.text = ""
        self.construieste_grila()
        self._mesaj("Sters pentru %s" % self.zi_selectata.strftime("%d %B %Y"))

    def _mesaj(self, text):
        popup = Popup(
            title="", content=Label(text=text), size_hint=(0.7, 0.2), auto_dismiss=True
        )
        popup.open()
        from kivy.clock import Clock
        Clock.schedule_once(lambda *_: popup.dismiss(), 1.0)


class JurnalAlimentarApp(App):
    title = "Jurnal Alimentar"

    def build(self):
        Window.clearcolor = CULOARE_FUNDAL
        cale_db = os.path.join(self.user_data_dir, "jurnal_alimentar.db")
        self.db = BazaDeDate(cale_db)
        return EcranPrincipal(self.db)


if __name__ == "__main__":
    JurnalAlimentarApp().run()
