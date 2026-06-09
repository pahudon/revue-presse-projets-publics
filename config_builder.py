#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Éditeur de configuration de la revue de presse (programme autonome).

Ce petit logiciel à fenêtre permet de définir tes thèmes, leurs mots-clés et
leurs sources, puis d'enregistrer le tout dans un fichier config.json placé
DANS LE MÊME DOSSIER que ce programme (et que revue_presse.py).

Différences avec la version web :
  - il lit automatiquement le config.json existant à l'ouverture (il se
    souvient donc de ta dernière configuration) ;
  - il enregistre directement au bon endroit, sans passer par le dossier
    Téléchargements.

Lancement (depuis le dossier du projet) :
    python config_builder.py

Aucune installation requise : tkinter est livré avec Python sous Windows.
"""

import copy
import json
import os

# ===========================================================================
# Données de référence (aucune dépendance graphique ici, donc testable seul)
# ===========================================================================

# Médias proposés dans les listes déroulantes (suggestions, modifiables à la main).
MEDIAS_QC = [
    "Radio-Canada", "La Presse", "Le Devoir", "L'Actualité",
    "Journal de Montréal", "Journal de Québec",
    "Le Soleil", "Le Droit", "La Tribune", "Le Nouvelliste",
    "Le Quotidien", "La Voix de l'Est", "Les Affaires", "Métro",
    "Le Charlevoisien", "L'Hebdo Journal", "Le Courrier du Sud", "Courrier Laval",
    "L'Information du Nord", "L'Écho de La Tuque", "Le Manic", "Le Nord-Côtier",
    "Info Dimanche", "Le Placoteux", "La Frontière", "Le Citoyen",
    "Courrier Frontenac", "La Nouvelle Union", "L'Express de Drummondville",
    "Beauce Média", "EnBeauce.com", "Le Journal de Lévis", "Le Reflet",
    "Graffici", "L'Écho de Frontenac", "L'Étoile du Lac",
]

# Sources de base par défaut (sans L'Actualité, déplacée dans les suggestions).
DEFAULT_SOURCES_BASE = [
    "Radio-Canada", "La Presse", "Le Devoir",
    "Journal de Montréal", "Journal de Québec",
]

# Thèmes par défaut (utilisés si aucun config.json n'existe encore).
DEFAULT_THEMES = [
    {"nom": "Tramway de Québec",
     "mots": [{"t": "tramway de Québec", "e": True},
              {"t": "réseau structurant", "e": True},
              {"t": "RSTC", "e": True}],
     "decochees": [], "locales": []},
    {"nom": "REM",
     "mots": [{"t": "Réseau express métropolitain", "e": True},
              {"t": "REM de l'Est", "e": True}],
     "decochees": [], "locales": []},
    {"nom": "Ligne bleue",
     "mots": [{"t": "prolongement de la ligne bleue", "e": True},
              {"t": "ligne bleue métro Montréal", "e": False}],
     "decochees": [], "locales": []},
    {"nom": "TGV / Alto",
     "mots": [{"t": "train à grande vitesse Québec", "e": False},
              {"t": "Alto train Québec Toronto", "e": False},
              {"t": "TGF", "e": True}],
     "decochees": [], "locales": []},
]


def chemin_config():
    """Chemin du config.json, dans le même dossier que ce programme."""
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config.json")


def model_to_config(sources_base, themes):
    """Transforme le modèle interne en structure config.json."""
    projets = []
    for th in themes:
        sources = [s for s in sources_base if s not in th["decochees"]]
        sources += [s for s in th["locales"] if s]
        mots = []
        for kw in th["mots"]:
            t = kw["t"].strip()
            if not t:
                continue
            if kw["e"] and not (t.startswith('"') and t.endswith('"')):
                mots.append('"' + t + '"')
            else:
                mots.append(t)
        projets.append({
            "nom": th["nom"].strip(),
            "mots_cles": mots,
            "sources": sources,
        })
    return {"sources_base": list(sources_base), "projets": projets}


def config_to_model(cfg):
    """Transforme une structure config.json en modèle interne (sources_base, themes)."""
    sources_base = cfg.get("sources_base") or list(DEFAULT_SOURCES_BASE)
    themes = []
    for p in cfg.get("projets", []):
        sources = p.get("sources", [])
        locales = [s for s in sources if s not in sources_base]
        decochees = [s for s in sources_base if s not in sources]
        mots = []
        for m in p.get("mots_cles", []):
            exacte = m.startswith('"') and m.endswith('"')
            mots.append({"t": m[1:-1] if exacte else m, "e": exacte})
        themes.append({
            "nom": p.get("nom", "Sans nom"),
            "mots": mots,
            "decochees": decochees,
            "locales": locales,
        })
    return sources_base, themes


def charger_modele():
    """Charge le modèle depuis config.json s'il existe, sinon les valeurs par défaut.
    Renvoie (sources_base, themes, charge_depuis_fichier)."""
    p = chemin_config()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            sb, th = config_to_model(cfg)
            if th:
                return sb, th, True
        except (json.JSONDecodeError, OSError):
            pass
    return list(DEFAULT_SOURCES_BASE), copy.deepcopy(DEFAULT_THEMES), False


def sauvegarder_config(sources_base, themes):
    """Écrit le config.json dans le dossier du programme. Renvoie le chemin."""
    cfg = model_to_config(sources_base, themes)
    p = chemin_config()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return p


# ===========================================================================
# Interface graphique (tkinter importé ici pour garder la logique testable)
# ===========================================================================

def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox, font as tkfont

    # Palette alignée sur celle de la page Web.
    ENCRE = "#1c1c1c"
    PAPIER = "#ffffff"
    ACCENT = "#0c4466"
    CARTE = "#efefef"
    GRIS = "#6b6b6b"
    LIGNE = "#dcdcdc"

    class ScrollableFrame(ttk.Frame):
        """Cadre défilant verticalement (pour la liste des thèmes)."""
        def __init__(self, parent):
            super().__init__(parent)
            self.canvas = tk.Canvas(self, highlightthickness=0, bg=PAPIER)
            self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
            self.inner = ttk.Frame(self.canvas)
            self.inner.bind(
                "<Configure>",
                lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
            self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
            self.canvas.bind(
                "<Configure>",
                lambda e: self.canvas.itemconfig(self.win, width=e.width))
            self.canvas.configure(yscrollcommand=self.scroll.set)
            self.canvas.pack(side="left", fill="both", expand=True)
            self.scroll.pack(side="right", fill="y")
            self.canvas.bind("<Enter>", self._bind_molette)
            self.canvas.bind("<Leave>", self._debind_molette)

        def _bind_molette(self, _):
            self.canvas.bind_all("<MouseWheel>", self._molette)

        def _debind_molette(self, _):
            self.canvas.unbind_all("<MouseWheel>")

        def _molette(self, e):
            self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    class App:
        def __init__(self, root):
            self.root = root
            self.sources_base, self.themes, charge = charger_modele()
            self.theme_widgets = []

            # Détection des polices IBM Plex (sinon repli vers les polices système).
            familles = set(tkfont.families())
            SANS = "IBM Plex Sans" if "IBM Plex Sans" in familles else "Segoe UI"
            SERIF = "IBM Plex Serif" if "IBM Plex Serif" in familles else "Georgia"
            self.SANS = SANS
            self.SERIF = SERIF

            root.title("Configuration de la revue de presse")
            root.geometry("860x720")
            root.minsize(720, 560)
            root.configure(bg=PAPIER)

            style = ttk.Style()
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
            style.configure(".", background=PAPIER, foreground=ENCRE,
                            font=(SANS, 10))
            style.configure("TFrame", background=PAPIER)
            style.configure("Carte.TFrame", background=CARTE, relief="solid", borderwidth=1)
            style.configure("TLabel", background=PAPIER, foreground=ENCRE)
            style.configure("Titre.TLabel", font=(SERIF, 14, "bold"), foreground=ACCENT)
            style.configure("Champ.TLabel", font=(SANS, 8, "bold"), foreground=ACCENT)
            style.configure("TButton", font=(SANS, 9))
            style.configure("Accent.TButton", font=(SANS, 9, "bold"))
            style.configure("TCheckbutton", background=CARTE)

            # En-tête
            tk.Frame(root, height=5, bg=ACCENT).pack(fill="x")
            tete = tk.Frame(root, bg=PAPIER)
            tete.pack(fill="x", padx=18, pady=(14, 6))
            tk.Label(tete, text="CONFIGURATION", bg=PAPIER, fg=ACCENT,
                     font=(SANS, 8, "bold")).pack(anchor="w")
            tk.Label(tete, text="Revue de presse : projets publics",
                     bg=PAPIER, fg=ENCRE, font=(SERIF, 18, "bold")).pack(anchor="w")
            etat = "config.json chargé" if charge else "valeurs par défaut (aucun config.json trouvé)"
            self.lbl_etat = tk.Label(tete, text="Départ : " + etat, bg=PAPIER,
                                     fg=GRIS, font=(SANS, 9))
            self.lbl_etat.pack(anchor="w")

            # Sources de base
            cadre_base = ttk.Frame(root)
            cadre_base.pack(fill="x", padx=18, pady=(8, 4))
            ttk.Label(cadre_base, text="Sources de base", style="Titre.TLabel").pack(anchor="w")
            ttk.Label(cadre_base,
                      text="Proposées et cochées par défaut dans chaque thème.").pack(anchor="w")
            self.zone_base = ttk.Frame(cadre_base)
            self.zone_base.pack(fill="x", pady=6)
            ajout_base = ttk.Frame(cadre_base)
            ajout_base.pack(fill="x")
            self.combo_base = ttk.Combobox(ajout_base, values=MEDIAS_QC, width=40)
            self.combo_base.pack(side="left", padx=(0, 6))
            ttk.Button(ajout_base, text="Ajouter cette source de base",
                       command=self.ajouter_base).pack(side="left")

            # Barre du bas en deux lignes empilées : chemin du fichier en
            # haut, boutons en dessous. C'est la disposition la plus robuste :
            # peu importe la longueur du chemin (OneDrive, etc.), les boutons
            # restent toujours visibles sur leur propre ligne.
            barre = tk.Frame(root, bg=CARTE, highlightthickness=1,
                             highlightbackground=LIGNE)
            barre.pack(fill="x", side="bottom")

            # Ligne 1 : chemin du fichier (tronqué visuellement si trop long).
            chemin = chemin_config()
            chemin_affiche = chemin if len(chemin) <= 90 else "..." + chemin[-87:]
            self.lbl_chemin = tk.Label(
                barre, text="Enregistre dans : " + chemin_affiche,
                bg=CARTE, fg=GRIS, font=(SANS, 8), anchor="w")
            self.lbl_chemin.pack(fill="x", padx=12, pady=(8, 0))

            # Ligne 2 : boutons alignés à droite.
            ligne_btns = tk.Frame(barre, bg=CARTE)
            ligne_btns.pack(fill="x", padx=8, pady=(4, 8))
            ttk.Button(ligne_btns, text="Enregistrer config.json",
                       style="Accent.TButton",
                       command=self.enregistrer).pack(side="right", padx=(6, 4))
            ttk.Button(ligne_btns, text="Recharger depuis config.json",
                       command=self.recharger).pack(side="right", padx=6)

            # Thèmes (zone défilante)
            cadre_th = ttk.Frame(root)
            cadre_th.pack(fill="both", expand=True, padx=18, pady=(10, 4))
            ligne = ttk.Frame(cadre_th)
            ligne.pack(fill="x")
            ttk.Label(ligne, text="Thèmes suivis", style="Titre.TLabel").pack(side="left", anchor="w")
            ttk.Button(ligne, text="+ Ajouter un thème",
                       command=self.ajouter_theme).pack(side="right")
            self.defilant = ScrollableFrame(cadre_th)
            self.defilant.pack(fill="both", expand=True, pady=6)

            self.rendre_base()
            self.rendre_themes()

        # ---- Synchronisation widgets -> modèle ----
        def sync(self):
            for ti, refs in enumerate(self.theme_widgets):
                th = self.themes[ti]
                th["nom"] = refs["nom"].get()
                th["mots"] = [{"t": tv.get(), "e": ev.get()} for tv, ev in refs["mots"]]
                th["decochees"] = [s for s, var in refs["base"].items() if not var.get()]

        # ---- Rendu : sources de base ----
        def rendre_base(self):
            for w in self.zone_base.winfo_children():
                w.destroy()
            for i, src in enumerate(self.sources_base):
                puce = ttk.Frame(self.zone_base)
                puce.pack(side="left", padx=(0, 8), pady=2)
                ttk.Label(puce, text=src).pack(side="left")
                ttk.Button(puce, text="✕", width=3,
                           command=lambda idx=i: self.retirer_base(idx)).pack(side="left", padx=(3, 0))

        def ajouter_base(self):
            self.sync()
            v = self.combo_base.get().strip()
            if v and v not in self.sources_base:
                self.sources_base.append(v)
                self.combo_base.set("")
                self.rendre_base()
                self.rendre_themes()

        def retirer_base(self, idx):
            self.sync()
            src = self.sources_base.pop(idx)
            for th in self.themes:
                th["decochees"] = [s for s in th["decochees"] if s != src]
            self.rendre_base()
            self.rendre_themes()

        # ---- Rendu : thèmes ----
        def rendre_themes(self):
            for w in self.defilant.inner.winfo_children():
                w.destroy()
            self.theme_widgets = []

            for ti, th in enumerate(self.themes):
                refs = {"mots": [], "base": {}}
                carte = ttk.Frame(self.defilant.inner, style="Carte.TFrame")
                carte.pack(fill="x", expand=True, pady=6, padx=2, ipady=6, ipadx=6)

                # En-tête du thème : nom + suppression
                tete = ttk.Frame(carte)
                tete.pack(fill="x", padx=8, pady=(6, 2))
                refs["nom"] = tk.StringVar(value=th["nom"])
                e = ttk.Entry(tete, textvariable=refs["nom"], font=(self.SERIF, 12, "bold"))
                e.pack(side="left", fill="x", expand=True)
                ttk.Button(tete, text="Supprimer ce thème",
                           command=lambda i=ti: self.supprimer_theme(i)).pack(side="right")

                # Mots-clés
                ttk.Label(carte, text="MOTS-CLÉS", style="Champ.TLabel").pack(anchor="w", padx=8, pady=(6, 2))
                zone_mots = ttk.Frame(carte)
                zone_mots.pack(fill="x", padx=8)
                for ki, kw in enumerate(th["mots"]):
                    rang = ttk.Frame(zone_mots)
                    rang.pack(fill="x", pady=1)
                    tv = tk.StringVar(value=kw["t"])
                    ev = tk.BooleanVar(value=kw["e"])
                    ttk.Entry(rang, textvariable=tv).pack(side="left", fill="x", expand=True)
                    ttk.Checkbutton(rang, text="exacte", variable=ev).pack(side="left", padx=6)
                    ttk.Button(rang, text="✕", width=3,
                               command=lambda i=ti, k=ki: self.retirer_mot(i, k)).pack(side="left")
                    refs["mots"].append((tv, ev))
                ajout_mot = ttk.Frame(carte)
                ajout_mot.pack(fill="x", padx=8, pady=(2, 4))
                refs["nouveau_mot"] = tk.StringVar()
                ttk.Entry(ajout_mot, textvariable=refs["nouveau_mot"]).pack(side="left", fill="x", expand=True)
                ttk.Button(ajout_mot, text="Ajouter un mot-clé",
                           command=lambda i=ti: self.ajouter_mot(i)).pack(side="left", padx=(6, 0))

                # Sources du thème
                ttk.Label(carte, text="SOURCES POUR CE THÈME", style="Champ.TLabel").pack(anchor="w", padx=8, pady=(6, 2))
                grille = ttk.Frame(carte)
                grille.pack(fill="x", padx=8)
                col = 0
                row = 0
                for src in self.sources_base:
                    var = tk.BooleanVar(value=src not in th["decochees"])
                    cb = ttk.Checkbutton(grille, text=src, variable=var)
                    cb.grid(row=row, column=col, sticky="w", padx=(0, 14), pady=1)
                    refs["base"][src] = var
                    col += 1
                    if col >= 3:
                        col = 0
                        row += 1
                # Sources locales
                if th["locales"]:
                    locz = ttk.Frame(carte)
                    locz.pack(fill="x", padx=8, pady=(4, 0))
                    for li, loc in enumerate(th["locales"]):
                        puce = ttk.Frame(locz)
                        puce.pack(side="left", padx=(0, 8))
                        ttk.Label(puce, text=loc + " (locale)").pack(side="left")
                        ttk.Button(puce, text="✕", width=3,
                                   command=lambda i=ti, l=li: self.retirer_locale(i, l)).pack(side="left", padx=(3, 0))
                ajout_loc = ttk.Frame(carte)
                ajout_loc.pack(fill="x", padx=8, pady=(4, 8))
                refs["combo_loc"] = ttk.Combobox(ajout_loc, values=MEDIAS_QC, width=36)
                refs["combo_loc"].pack(side="left")
                ttk.Button(ajout_loc, text="Ajouter une source locale",
                           command=lambda i=ti: self.ajouter_locale(i)).pack(side="left", padx=(6, 0))

                self.theme_widgets.append(refs)

        # ---- Handlers structurels ----
        def _conserver_defilement(self, fonction):
            """Exécute une action qui rebâtit l'interface en gardant la même
            position de défilement à l'écran. Sans ça, l'ajout/retrait d'un
            mot-clé replace l'utilisateur au milieu de la liste."""
            top, _ = self.defilant.canvas.yview()
            fonction()
            # update_idletasks force Tk à recalculer les dimensions avant qu'on
            # remette le défilement à sa place.
            self.defilant.canvas.update_idletasks()
            self.defilant.canvas.yview_moveto(top)

        def _defiler_jusqu_en_bas(self, fonction):
            """Exécute l'action puis défile jusqu'au bas (pour voir un nouveau
            thème qu'on vient d'ajouter)."""
            fonction()
            self.defilant.canvas.update_idletasks()
            self.defilant.canvas.yview_moveto(1.0)

        def ajouter_theme(self):
            def _action():
                self.sync()
                self.themes.append({"nom": "Nouveau thème", "mots": [],
                                    "decochees": [], "locales": []})
                self.rendre_themes()
            self._defiler_jusqu_en_bas(_action)

        def supprimer_theme(self, i):
            def _action():
                self.sync()
                del self.themes[i]
                self.rendre_themes()
            self._conserver_defilement(_action)

        def ajouter_mot(self, i):
            def _action():
                self.sync()
                v = self.theme_widgets[i]["nouveau_mot"].get().strip()
                if v:
                    self.themes[i]["mots"].append({"t": v, "e": (" " in v)})
                    self.rendre_themes()
            self._conserver_defilement(_action)

        def retirer_mot(self, i, k):
            def _action():
                self.sync()
                del self.themes[i]["mots"][k]
                self.rendre_themes()
            self._conserver_defilement(_action)

        def ajouter_locale(self, i):
            def _action():
                self.sync()
                v = self.theme_widgets[i]["combo_loc"].get().strip()
                if v and v not in self.themes[i]["locales"]:
                    self.themes[i]["locales"].append(v)
                    self.rendre_themes()
            self._conserver_defilement(_action)

        def retirer_locale(self, i, l):
            def _action():
                self.sync()
                del self.themes[i]["locales"][l]
                self.rendre_themes()
            self._conserver_defilement(_action)

        # ---- Enregistrement / rechargement ----
        def enregistrer(self):
            self.sync()
            noms = [t["nom"].strip() for t in self.themes if t["nom"].strip()]
            if not noms:
                messagebox.showwarning("Rien à enregistrer",
                                       "Ajoute au moins un thème avec un nom.")
                return
            p = sauvegarder_config(self.sources_base, self.themes)
            self.lbl_etat.config(text="Dernier enregistrement réussi.")
            messagebox.showinfo("Enregistré",
                                "Configuration enregistrée dans :\n" + p)

        def recharger(self):
            if not os.path.exists(chemin_config()):
                messagebox.showinfo("Aucun fichier",
                                    "Pas de config.json dans ce dossier pour l'instant.")
                return
            self.sources_base, self.themes, _ = charger_modele()
            self.rendre_base()
            self.rendre_themes()
            self.lbl_etat.config(text="Rechargé depuis config.json.")

    # Avant de créer la fenêtre, on dit à Windows que ce programme dessine
    # nativement en haute résolution. Sans ça, sur un écran à 125%, 150% ou
    # plus de mise à l'échelle, Windows rend la fenêtre en basse résolution
    # puis l'agrandit par interpolation : tout devient flou.
    _activer_haute_resolution_windows()

    root = tk.Tk()

    # Ajuste l'échelle interne de tkinter au DPI réel de l'écran, pour que
    # les tailles de police restent justes maintenant que l'application est
    # consciente du DPI.
    try:
        dpi = root.winfo_fpixels("1i")  # pixels par pouce mesurés
        root.tk.call("tk", "scaling", dpi / 72.0)
    except tk.TclError:
        pass

    App(root)
    root.mainloop()


def _activer_haute_resolution_windows():
    """Déclare l'application "DPI-aware" sur Windows, pour un rendu net
    des polices sur les écrans à haute densité. Sans effet sur les autres
    systèmes d'exploitation et silencieux si Windows est trop vieux."""
    import sys
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # Windows 8.1 et plus récent : per-monitor DPI aware.
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            # Repli pour Windows 7 / 8.
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


if __name__ == "__main__":
    run_gui()
