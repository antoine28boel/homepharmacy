"""Armoire à pharmacie : produits, liste de courses, et croisement avec le catalogue."""

import calendar
import json
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from . import catalogue as cat

BIENTOT_JOURS = 90
COLLYRE_OUVERT_JOURS = 28
FORMES = ["comprimé", "gélule", "sirop", "sachet", "spray", "gouttes", "collyre", "crème", "gel", "pommade",
          "suppositoire", "ovule", "pastille", "pansement", "matériel", "autre"]
CHAMPS = ("nom", "substances_texte", "dosage", "forme", "peremption", "ouvert_le", "emplacement", "notes", "photo")
PHOTO_MAX = 200_000  # vignette seulement


class Invalide(ValueError):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS produits (
    id INTEGER PRIMARY KEY,
    nom TEXT NOT NULL,
    substances_texte TEXT NOT NULL DEFAULT '',
    substances TEXT NOT NULL DEFAULT '[]',
    maux_perso TEXT NOT NULL DEFAULT '[]',
    dosage TEXT NOT NULL DEFAULT '',
    forme TEXT NOT NULL DEFAULT '',
    quantite INTEGER NOT NULL DEFAULT 1,
    peremption TEXT NOT NULL DEFAULT '',
    ouvert_le TEXT NOT NULL DEFAULT '',
    emplacement TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    photo TEXT NOT NULL DEFAULT '',
    cree_le TEXT NOT NULL DEFAULT (date('now')),
    maj_le TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY,
    libelle TEXT NOT NULL UNIQUE,
    cree_le TEXT NOT NULL DEFAULT (date('now'))
);
"""


def ouvrir(chemin):
    Path(chemin).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(chemin, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def normaliser_peremption(texte):
    """Ramène « 03/2027 », « EXP 03-27 », « 2027-03 » ou « 31/03/2027 » à AAAA-MM. Vide si illisible."""
    t = str(texte or "").strip()
    if not t:
        return ""
    m = re.search(r"(?<!\d)(20\d{2})[-/. ](0?[1-9]|1[0-2])(?![\d])", t)
    if m:
        return f"{m[1]}-{int(m[2]):02d}"
    m = re.search(r"(?<!\d)(?:\d{1,2}[-/. ])?(0?[1-9]|1[0-2])[-/. ](20\d{2}|\d{2})(?!\d)", t)
    if m:
        annee = int(m[2]) + (2000 if len(m[2]) == 2 else 0)
        return f"{annee}-{int(m[1]):02d}"
    return ""


def fin_de_validite(peremption):
    """Une date sans jour vaut jusqu'au dernier jour du mois."""
    annee, mois = map(int, peremption.split("-"))
    return date(annee, mois, calendar.monthrange(annee, mois)[1])


def etat_produit(p, aujourd_hui=None):
    """(état, message) : perime, epuise, ouvert_trop_longtemps, bientot, ok, ou inconnu si pas de date."""
    aujourd_hui = aujourd_hui or date.today()
    if p["peremption"]:
        fin = fin_de_validite(p["peremption"])
        if fin < aujourd_hui:
            return "perime", "Périmé : à rapporter à la pharmacie"
    if p["quantite"] <= 0:
        return "epuise", "Plus en stock"
    if p["forme"] == "collyre" and p["ouvert_le"]:
        if date.fromisoformat(p["ouvert_le"]) + timedelta(days=COLLYRE_OUVERT_JOURS) < aujourd_hui:
            return "ouvert_trop_longtemps", "Ouvert depuis plus de 4 semaines : vérifiez la notice"
    if not p["peremption"]:
        return "inconnu", "Date de péremption à renseigner"
    if fin <= aujourd_hui + timedelta(days=BIENTOT_JOURS):
        return "bientot", "Périme bientôt"
    return "ok", ""


def _ligne(r, avec_photo=True):
    p = dict(r)
    p["substances"] = json.loads(p["substances"])
    p["maux_perso"] = json.loads(p["maux_perso"])
    p["etat"], p["etat_message"] = etat_produit(p)
    p["substances_noms"] = [cat.SUBSTANCES[c]["nom"] for c in p["substances"] if c in cat.SUBSTANCES]
    p["alertes"] = [cat.SUBSTANCES[c]["role"] for c in p["substances"]
                    if cat.SUBSTANCES[c].get("deconseille") or cat.SUBSTANCES[c].get("prescription")]
    if not avec_photo:
        p.pop("photo", None)
    return p


def _valider(d, partiel=False):
    """Champs nettoyés d'un produit. Refuse ce qui n'a pas de sens plutôt que de le stocker."""
    v = {}
    for c in CHAMPS:
        if c in d:
            v[c] = str(d[c] or "").strip()
    if not partiel and not v.get("nom"):
        raise Invalide("Le nom du produit est obligatoire")
    if "nom" in v and not v["nom"]:
        raise Invalide("Le nom du produit est obligatoire")
    if "peremption" in v:
        brut = v["peremption"]
        v["peremption"] = normaliser_peremption(brut)
        if brut and not v["peremption"]:
            raise Invalide("Date de péremption illisible : indiquez le mois et l'année, par exemple 03/2027")
    if v.get("ouvert_le"):
        try:
            date.fromisoformat(v["ouvert_le"])
        except ValueError:
            raise Invalide("Date d'ouverture illisible")
    if v.get("forme") and v["forme"] not in FORMES:
        v["forme"] = "autre"
    if len(v.get("photo", "")) > PHOTO_MAX:
        raise Invalide("Photo trop lourde")
    if v.get("photo") and not v["photo"].startswith("data:image/"):
        raise Invalide("Photo invalide")
    if "quantite" in d:
        try:
            v["quantite"] = int(d["quantite"])
        except (TypeError, ValueError):
            raise Invalide("Quantité invalide")
        if not 0 <= v["quantite"] <= 999:
            raise Invalide("Quantité invalide")
    if "substances" in d:
        cles = d["substances"]
        if not isinstance(cles, list) or any(c not in cat.SUBSTANCES for c in cles):
            raise Invalide("Substance inconnue")
        v["substances"] = json.dumps([c for c in cat.SUBSTANCES if c in cles])
    elif not partiel:
        # Le texte de la boîte prime : le nom de marque ne sert que si aucune substance n'est écrite.
        cles = cat.trouver_substances(v.get("substances_texte", "")) or cat.trouver_substances(v["nom"])
        v["substances"] = json.dumps(cles)
    if "maux_perso" in d:
        cles = d["maux_perso"]
        if not isinstance(cles, list) or any(c not in cat.MAUX for c in cles):
            raise Invalide("Mal inconnu")
        v["maux_perso"] = json.dumps(cles)
    return v


def lister(conn, avec_photo=True):
    return [_ligne(r, avec_photo) for r in conn.execute("SELECT * FROM produits ORDER BY nom COLLATE NOCASE, peremption")]


def lire(conn, pid):
    r = conn.execute("SELECT * FROM produits WHERE id=?", (pid,)).fetchone()
    return _ligne(r) if r else None


def ajouter(conn, d):
    v = _valider(d)
    v.setdefault("quantite", 1)
    cols = ",".join(v)
    cur = conn.execute(f"INSERT INTO produits ({cols}) VALUES ({','.join('?' * len(v))})", list(v.values()))
    return lire(conn, cur.lastrowid)


def modifier(conn, pid, d):
    v = _valider(d, partiel=True)
    if "substances_texte" in v and "substances" not in v:
        trouve = cat.trouver_substances(v["substances_texte"])
        if trouve:
            v["substances"] = json.dumps(trouve)
    if v:
        reglage = ",".join(f"{c}=?" for c in v)
        conn.execute(f"UPDATE produits SET {reglage}, maj_le=datetime('now') WHERE id=?", [*v.values(), pid])
    return lire(conn, pid)


def supprimer(conn, pid):
    return conn.execute("DELETE FROM produits WHERE id=?", (pid,)).rowcount > 0


def courses(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM courses ORDER BY cree_le, id")]


def ajouter_course(conn, libelle):
    libelle = str(libelle or "").strip()
    if not libelle:
        raise Invalide("Indiquez ce qu'il faut acheter")
    conn.execute("INSERT OR IGNORE INTO courses (libelle) VALUES (?)", (libelle,))
    return courses(conn)


def supprimer_course(conn, cid):
    return conn.execute("DELETE FROM courses WHERE id=?", (cid,)).rowcount > 0


def _utilisable(p):
    return p["etat"] in ("ok", "bientot", "inconnu")


def _risques(p):
    return [c for c in p["substances"] if cat.SUBSTANCES[c].get("deconseille") or cat.SUBSTANCES[c].get("prescription")]


def _propose_pour(p, cle):
    """Une association avec une substance à risque n'est pas un simple produit de cette substance :
    un sachet paracétamol + pseudoéphédrine ne doit pas sortir pour une fièvre."""
    return cle in p["substances"] and not set(_risques(p)) - {cle}


def _fiche_substance(cle, produits):
    s = cat.SUBSTANCES[cle]
    return {"cle": cle, "nom": s["nom"], "role": s["role"], "type": s.get("type", "medicament"),
            "duree": s.get("duree", ""), "precautions": s["precautions"],
            "sur_avis": bool(s.get("prescription")),
            "produits": [p for p in produits if _propose_pour(p, cle)]}


def conseils(conn, cle):
    """Fiche d'un mal : signes d'alerte, ce qu'on a, ce qu'il faudrait, doublons à ne pas cumuler."""
    m = cat.MAUX.get(cle)
    if not m:
        return None
    tous = lister(conn, avec_photo=False)
    utilisables = [p for p in tous if _utilisable(p)]
    principal = [_fiche_substance(c, utilisables) for c in m["principal"]]
    aussi = [_fiche_substance(c, utilisables) for c in m["aussi"]]
    proposees = {c for c in m["principal"] + m["aussi"]}
    # Présent mais inutilisable : on le dit, pour éviter de le prendre quand même.
    a_ecarter = []
    for p in tous:
        if not proposees & set(p["substances"]):
            continue
        if p["etat"] == "perime":
            a_ecarter.append({**p, "raison": "Périmé"})
        elif _utilisable(p) and not any(_propose_pour(p, c) for c in proposees):
            noms = ", ".join(cat.SUBSTANCES[c]["nom"] for c in _risques(p))
            a_ecarter.append({**p, "raison": f"Contient aussi : {noms}. Demandez conseil."})
    perso = [p for p in utilisables if cle in p["maux_perso"] and not proposees & set(p["substances"])]
    return {
        "cle": cle, "nom": m["nom"], "groupe": m["groupe"], "gestes": m["gestes"],
        "urgence": m.get("urgence", []), "consulter": m.get("consulter", []),
        "principal": principal, "aussi": aussi, "a_ecarter": a_ecarter, "perso": perso,
        "manque": [s["nom"] for s in principal if not s["produits"]],
        "cumul": doublons(utilisables, proposees),
    }


def doublons(produits, cles_proposees=None):
    """Classes présentes dans plusieurs produits : le risque classique est de cumuler sans le savoir."""
    classes = {}
    for p in produits:
        for c in p["substances"]:
            s = cat.SUBSTANCES[c]
            if s.get("type") == "soin" or (cles_proposees is not None and c not in cles_proposees):
                continue
            classes.setdefault(s["classe"], {"noms": set(), "produits": set()})
            classes[s["classe"]]["noms"].add(s["nom"])
            classes[s["classe"]]["produits"].add(p["nom"])
    sortie = []
    for infos in classes.values():
        if len(infos["produits"]) > 1:
            sortie.append({"substance": " / ".join(sorted(infos["noms"])), "produits": sorted(infos["produits"])})
    return sortie


def liste_maux(conn):
    utilisables = [p for p in lister(conn, avec_photo=False) if _utilisable(p)]
    presentes = {c for p in utilisables for c in p["substances"] if _propose_pour(p, c)}
    perso = {m for p in utilisables for m in p["maux_perso"]}
    return [{"cle": k, "nom": m["nom"], "groupe": m["groupe"], "mots": m.get("mots", []),
             "disponible": bool(presentes & set(m["principal"] + m["aussi"])) or k in perso}
            for k, m in cat.MAUX.items()]


def resume(conn):
    produits = lister(conn, avec_photo=False)
    etats = {}
    for p in produits:
        etats.setdefault(p["etat"], []).append(p)
    presentes = {c for p in produits if _utilisable(p) for c in p["substances"] if _propose_pour(p, c)}
    return {
        "produits": sum(1 for p in produits if p["quantite"] > 0),
        "perimes": etats.get("perime", []),
        "bientot": etats.get("bientot", []),
        "epuises": etats.get("epuise", []),
        "a_verifier": etats.get("ouvert_trop_longtemps", []) + etats.get("inconnu", []),
        "courses": courses(conn),
        "essentiels": [{"cle": c, "nom": cat.SUBSTANCES[c]["nom"], "present": c in presentes} for c in cat.ESSENTIELS],
    }


def exporter(conn):
    return {"format": "pharmacie", "version": 1, "produits": lister(conn), "courses": courses(conn)}
