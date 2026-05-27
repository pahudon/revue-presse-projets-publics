#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Revue de presse quotidienne sur les grands projets publics au Québec.

Comportement :
  - récupère les articles récents via les flux RSS de Google Actualités
    (un flux par projet), uniquement pour une liste blanche de médias ;
  - accumule tout dans une archive permanente (revue_data.json) sans doublon ;
  - génère une page web (index.html) qui affiche les 3 derniers mois par projet.

Usage :
    python3 revue_presse.py

Dépendance :
    pip install feedparser
"""

import html
import json
import unicodedata
import urllib.parse
from datetime import datetime, timedelta, timezone

import feedparser

# ===========================================================================
# 1. CONFIGURATION
# ===========================================================================

# --- Projets suivis -------------------------------------------------------
# Étiquette affichée -> liste de mots-clés (combinés avec OR).
# Pour un sigle ambigu (REM, etc.), privilégie le nom complet.
PROJETS = {
    "Tramway de Québec": [
        '"tramway de Québec"',
        '"réseau structurant"',
        '"RSTC"',
    ],
    "REM": [
        '"Réseau express métropolitain"',
        '"REM de l\'Est"',
    ],
    "Ligne bleue": [
        '"prolongement de la ligne bleue"',
        '"ligne bleue" métro Montréal',
    ],
    "TGV / Alto": [
        '"train à grande vitesse" Québec',
        '"Alto" train Québec Toronto',
        '"TGF"',
    ],
}

# --- Liste blanche des médias --------------------------------------------
# Le script ne garde que les articles publiés par ces sources.
# La comparaison est tolérante (accents, majuscules et apostrophes ignorés).
# Pour ajouter ou retirer un média, modifie simplement cette liste.
SOURCES_AUTORISEES = [
    "Radio-Canada",
    "La Presse",
    "Le Devoir",
    "Journal de Montréal",
    "Journal de Québec",
]

# --- Fenêtres de temps ----------------------------------------------------
# Récupération à chaque exécution : filet de sécurité si tu sautes des jours.
# Au premier lancement, ça détermine aussi jusqu'où on remonte pour démarrer
# l'archive (Google limite la profondeur, donc l'archive se remplit surtout
# au fil du temps, jour après jour).
FENETRE_FETCH_JOURS = 30

# Ce qui s'affiche dans les sections par projet : les 3 derniers mois.
JOURS_AFFICHAGE = 90

# --- Divers ---------------------------------------------------------------
PARAMS_REGION = "hl=fr-CA&gl=CA&ceid=CA:fr"
FICHIER_SORTIE = "index.html"
FICHIER_ARCHIVE = "revue_data.json"
FICHIER_CONFIG = "config.json"  # produit par l'éditeur config_builder.html


# ===========================================================================
# 2. OUTILS
# ===========================================================================

def normaliser(texte):
    """Minuscules, sans accents, sans apostrophes, espaces simples."""
    texte = texte.lower()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    texte = texte.replace("'", " ").replace("\u2019", " ")
    return " ".join(texte.split())


def source_autorisee(nom_source, sources_ok):
    """Vrai si la source figure dans la liste fournie (comparaison tolérante)."""
    nom = normaliser(nom_source)
    for autorisee in sources_ok:
        if normaliser(autorisee) in nom:
            return True
    return False


def charger_config():
    """Charge les thèmes depuis config.json s'il existe, sinon utilise les
    valeurs internes (PROJETS + SOURCES_AUTORISEES). Renvoie une liste de
    dictionnaires : {nom, mots_cles, sources}, chaque thème ayant ses sources."""
    try:
        with open(FICHIER_CONFIG, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        base = cfg.get("sources_base", SOURCES_AUTORISEES)
        themes = []
        for p in cfg.get("projets", []):
            themes.append({
                "nom": p.get("nom", "Sans nom"),
                "mots_cles": p.get("mots_cles", []),
                "sources": p.get("sources") or base,
            })
        if themes:
            print(f"  Configuration chargée depuis {FICHIER_CONFIG} : {len(themes)} thème(s).")
            return themes
        print(f"  {FICHIER_CONFIG} vide : utilisation des réglages internes.")
    except FileNotFoundError:
        print(f"  Pas de {FICHIER_CONFIG} : utilisation des réglages internes.")
    except (json.JSONDecodeError, KeyError) as err:
        print(f"  {FICHIER_CONFIG} illisible ({err}) : utilisation des réglages internes.")
    # Repli sur les valeurs internes
    return [{"nom": nom, "mots_cles": mc, "sources": SOURCES_AUTORISEES}
            for nom, mc in PROJETS.items()]


# ===========================================================================
# 3. RÉCUPÉRATION DES FLUX
# ===========================================================================

def url_google_news(mots_cles):
    """URL du flux RSS Google Actualités pour une liste de mots-clés."""
    requete = " OR ".join(mots_cles)
    requete = f"({requete}) when:{FENETRE_FETCH_JOURS}d"
    return (f"https://news.google.com/rss/search?"
            f"q={urllib.parse.quote(requete)}&{PARAMS_REGION}")


def nom_source(entree):
    source = entree.get("source", {})
    if source and source.get("title"):
        return source["title"]
    titre = entree.get("title", "")
    if " - " in titre:
        return titre.rsplit(" - ", 1)[1]
    return "Source inconnue"


def titre_propre(entree):
    titre = entree.get("title", "")
    source = entree.get("source", {})
    if source and source.get("title") and titre.endswith(" - " + source["title"]):
        return titre[: -(len(source["title"]) + 3)]
    if " - " in titre:
        return titre.rsplit(" - ", 1)[0]
    return titre


def recuperer_nouveaux(projets):
    """Récupère les articles récents. Chaque thème est filtré selon SES propres
    sources (sources de base éventuellement complétées de médias locaux)."""
    nouveaux = []
    vus = set()
    for theme in projets:
        nom_projet = theme["nom"]
        sources_ok = theme["sources"]
        print(f"  Récupération : {nom_projet} ...")
        flux = feedparser.parse(url_google_news(theme["mots_cles"]))
        for entree in flux.entries:
            source = nom_source(entree)
            if not source_autorisee(source, sources_ok):
                continue
            titre = titre_propre(entree)
            cle = normaliser(titre)
            if cle in vus:
                continue
            vus.add(cle)
            if entree.get("published_parsed"):
                date_pub = datetime(*entree.published_parsed[:6], tzinfo=timezone.utc)
            else:
                date_pub = datetime.now(timezone.utc)
            nouveaux.append({
                "titre": titre,
                "lien": entree.get("link", "#"),
                "source": source,
                "date": date_pub.isoformat(),
                "projet": nom_projet,
            })
    return nouveaux


# ===========================================================================
# 4. ARCHIVE PERSISTANTE
# ===========================================================================

def charger_archive():
    try:
        with open(FICHIER_ARCHIVE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def sauvegarder_archive(articles):
    with open(FICHIER_ARCHIVE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


def fusionner(archive, nouveaux):
    """Ajoute les nouveaux articles absents de l'archive (clé = titre normalisé)."""
    deja = {normaliser(a["titre"]) for a in archive}
    ajoutes = 0
    for art in nouveaux:
        if normaliser(art["titre"]) not in deja:
            archive.append(art)
            deja.add(normaliser(art["titre"]))
            ajoutes += 1
    return archive, ajoutes


def date_obj(art):
    return datetime.fromisoformat(art["date"])


# ===========================================================================
# 5. GÉNÉRATION DE LA PAGE HTML
# ===========================================================================

MOIS_LONG = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]
MOIS_COURT = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.",
              "août", "sept.", "oct.", "nov.", "déc."]


def date_courte(dt):
    local = dt.astimezone()
    return f"{local.day} {MOIS_COURT[local.month - 1]} {local.year}"


def carte_html(art):
    return f"""        <article class="carte" data-projet="{html.escape(art['projet'])}" data-titre="{html.escape(normaliser(art['titre']))}" data-source="{html.escape(normaliser(art['source']))}" data-date="{html.escape(art['date'])}">
          <a class="lien" href="{html.escape(art['lien'])}" target="_blank" rel="noopener">
            <h3>{html.escape(art['titre'])}</h3>
          </a>
          <div class="meta">
            <span class="source">{html.escape(art['source'])}</span>
            <span class="sep">/</span>
            <time>{html.escape(date_courte(date_obj(art)))}</time>
          </div>
        </article>"""


def generer_html(archive, projets):
    maintenant = datetime.now(timezone.utc)
    limite = maintenant - timedelta(days=JOURS_AFFICHAGE)
    recents = [a for a in archive if date_obj(a) >= limite]

    noms_projets = [t["nom"] for t in projets]

    aujourdhui = datetime.now().astimezone()
    date_titre = f"{aujourdhui.day} {MOIS_LONG[aujourdhui.month - 1]} {aujourdhui.year}"

    # Sections par projet (3 derniers mois)
    par_projet = {nom: [] for nom in noms_projets}
    for a in recents:
        par_projet.setdefault(a["projet"], []).append(a)
    for p in par_projet:
        par_projet[p].sort(key=date_obj, reverse=True)

    boutons = ['<button class="filtre actif" data-projet="tous">Tous</button>']
    sections = []
    for projet, articles in par_projet.items():
        boutons.append(
            f'<button class="filtre" data-projet="{html.escape(projet)}">'
            f'{html.escape(projet)} <span class="compte">{len(articles)}</span></button>'
        )
        if articles:
            cartes = "\n".join(carte_html(a) for a in articles)
        else:
            cartes = '<p class="vide">Aucun article dans les 3 derniers mois.</p>'
        sections.append(f"""      <section class="bloc projet" data-projet="{html.escape(projet)}">
        <h2>{html.escape(projet)}</h2>
        <div class="cartes">
{cartes}
        </div>
      </section>""")

    boutons_html = "\n        ".join(boutons)
    sections_html = "\n".join(sections)
    total_recents = len(recents)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revue de presse : grands projets publics au Québec</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;1,9..144,400&family=Spline+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --encre: #1a1f2e; --papier: #f4f1ea; --carte: #fffefb;
    --accent: #9a3b2e; --accent-doux: #c46a4a; --gris: #6b6a64; --ligne: #ddd8cc;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Spline Sans', sans-serif; background: var(--papier);
    color: var(--encre); line-height: 1.5;
    background-image: radial-gradient(var(--ligne) 0.5px, transparent 0.5px);
    background-size: 22px 22px;
  }}
  .ruban {{ height: 6px; background: linear-gradient(90deg, var(--accent), var(--accent-doux)); }}
  header {{ max-width: 1100px; margin: 0 auto; padding: 48px 24px 28px; border-bottom: 2px solid var(--encre); }}
  .surtitre {{ font-size: 0.74rem; letter-spacing: 0.22em; text-transform: uppercase; color: var(--accent); font-weight: 600; }}
  h1 {{ font-family: 'Fraunces', serif; font-weight: 600; font-size: clamp(2rem, 5vw, 3.4rem); line-height: 1.05; margin: 10px 0 14px; letter-spacing: -0.01em; }}
  .sous {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: baseline; color: var(--gris); font-size: 0.92rem; }}
  .sous .date {{ font-style: italic; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px 80px; }}
  .barre {{ position: sticky; top: 0; z-index: 5; background: var(--papier); padding: 18px 0 14px; margin-bottom: 8px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; border-bottom: 1px solid var(--ligne); }}
  .filtre {{ font-family: inherit; font-size: 0.86rem; cursor: pointer; border: 1px solid var(--encre); background: transparent; color: var(--encre); padding: 6px 14px; border-radius: 999px; transition: all 0.15s; }}
  .filtre:hover, .filtre.actif {{ background: var(--encre); color: var(--papier); }}
  .compte {{ font-size: 0.7rem; opacity: 0.7; margin-left: 3px; }}
  .recherche {{ font-family: inherit; font-size: 0.9rem; border: none; border-bottom: 1.5px solid var(--encre); background: transparent; padding: 6px 4px; width: 220px; color: var(--encre); outline: none; }}
  .recherche::placeholder {{ color: var(--gris); }}
  .periode {{ margin-left: auto; font-family: inherit; font-size: 0.86rem; cursor: pointer; border: 1px solid var(--encre); background: transparent; color: var(--encre); padding: 5px 28px 5px 14px; border-radius: 999px; outline: none; -webkit-appearance: none; -moz-appearance: none; appearance: none; background-image: linear-gradient(45deg, transparent 50%, var(--encre) 50%), linear-gradient(135deg, var(--encre) 50%, transparent 50%); background-position: calc(100% - 14px) 50%, calc(100% - 9px) 50%; background-size: 5px 5px, 5px 5px; background-repeat: no-repeat; }}
  .periode:hover {{ background-color: var(--encre); color: var(--papier); background-image: linear-gradient(45deg, transparent 50%, var(--papier) 50%), linear-gradient(135deg, var(--papier) 50%, transparent 50%); }}
  .bloc {{ margin-top: 40px; }}
  .bloc h2 {{ font-family: 'Fraunces', serif; font-size: 1.5rem; font-weight: 600; padding-bottom: 8px; margin-bottom: 18px; border-bottom: 1px solid var(--ligne); position: relative; }}
  .bloc h2::before {{ content: ""; position: absolute; bottom: -1px; left: 0; width: 60px; height: 3px; background: var(--accent); }}
  .cartes {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }}
  .carte {{ background: var(--carte); border: 1px solid var(--ligne); border-radius: 8px; padding: 18px 20px; transition: transform 0.15s, box-shadow 0.15s; }}
  .carte:hover {{ transform: translateY(-3px); box-shadow: 0 10px 24px rgba(26,31,46,0.10); }}
  .carte h3 {{ font-family: 'Fraunces', serif; font-weight: 600; font-size: 1.08rem; line-height: 1.25; color: var(--encre); margin-top: 4px; }}
  .lien {{ text-decoration: none; }}
  .lien:hover h3 {{ color: var(--accent); }}
  .meta {{ margin-top: 12px; font-size: 0.8rem; color: var(--gris); display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
  .source {{ font-weight: 600; color: var(--accent-doux); }}
  .sep {{ opacity: 0.5; }}
  .vide {{ color: var(--gris); font-style: italic; grid-column: 1 / -1; }}
  .bloc.cache, .carte.cache {{ display: none; }}
  footer {{ max-width: 1100px; margin: 0 auto; padding: 24px; border-top: 1px solid var(--ligne); color: var(--gris); font-size: 0.8rem; }}
  footer code {{ background: #e8e3d8; padding: 1px 6px; border-radius: 4px; }}
</style>
</head>
<body>
  <div class="ruban"></div>
  <header>
    <div class="surtitre">Veille quotidienne</div>
    <h1>Grands projets publics au Québec</h1>
    <div class="sous">
      <span class="date">{date_titre}</span>
      <span>{total_recents} article{'s' if total_recents != 1 else ''} sur les 3 derniers mois</span>
      <span>{len(archive)} au total dans l'archive</span>
    </div>
  </header>
  <main>
    <div class="barre">
      {boutons_html}
      <select class="periode" id="periode" title="Période affichée">
        <option value="1">Dernières 24 h</option>
        <option value="7">7 derniers jours</option>
        <option value="14">14 derniers jours</option>
        <option value="30">30 derniers jours</option>
        <option value="90" selected>3 derniers mois</option>
      </select>
      <input class="recherche" type="search" placeholder="Chercher dans les titres...">
    </div>
{sections_html}
  </main>
  <footer>
    Généré le {date_titre} à partir des flux Google Actualités. L'éditeur <code>config_builder.py</code> permet de modifier les projets et les sources (fichier <code>config.json</code>). L'archive complète est conservée dans <code>revue_data.json</code>.
  </footer>

<script>
  const filtres = document.querySelectorAll('.filtre');
  const blocs = document.querySelectorAll('.bloc');
  const recherche = document.querySelector('.recherche');
  const periode = document.getElementById('periode');
  let projetActif = 'tous';

  function appliquer() {{
    const q = recherche.value.toLowerCase().trim();
    const jours = parseInt(periode.value, 10);
    const limite = Date.now() - jours * 86400000;
    blocs.forEach(bloc => {{
      let visibles = 0;
      bloc.querySelectorAll('.carte').forEach(c => {{
        const okProjet = (projetActif === 'tous' || c.dataset.projet === projetActif);
        const okTexte = !q || c.dataset.titre.includes(q) || c.dataset.source.includes(q);
        const okDate = Date.parse(c.dataset.date) >= limite;
        const visible = okProjet && okTexte && okDate;
        c.classList.toggle('cache', !visible);
        if (visible) visibles++;
      }});
      bloc.classList.toggle('cache', visibles === 0);
    }});
  }}

  filtres.forEach(b => b.addEventListener('click', () => {{
    filtres.forEach(x => x.classList.remove('actif'));
    b.classList.add('actif');
    projetActif = b.dataset.projet;
    appliquer();
  }}));
  recherche.addEventListener('input', appliquer);
  periode.addEventListener('change', appliquer);
</script>
</body>
</html>"""


# ===========================================================================
# 7. POINT D'ENTRÉE
# ===========================================================================

def main():
    print("Revue de presse : récupération des flux...")
    projets = charger_config()
    nouveaux = recuperer_nouveaux(projets)
    archive = charger_archive()
    archive, ajoutes = fusionner(archive, nouveaux)
    sauvegarder_archive(archive)
    page = generer_html(archive, projets)
    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Terminé : {ajoutes} nouveaux articles, {len(archive)} au total dans l'archive.")
    print(f"Page écrite dans {FICHIER_SORTIE}")


if __name__ == "__main__":
    main()
