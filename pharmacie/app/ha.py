"""Liens avec Home Assistant : capteurs publiés et lecture d'une boîte par l'IA (ai_task.generate_data)."""

import json
import logging
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path

from . import catalogue as cat
from . import stock

log = logging.getLogger("pharmacie")
SOUS_DOSSIER = "pharmacie"

INSTRUCTIONS = (
    "Les photos montrent une boîte de médicament ou un produit de soin. Recopie uniquement ce qui est écrit sur "
    "l'emballage, en français. N'invente rien : laisse vide ce qui n'est pas lisible, en particulier la date de "
    "péremption (mention EXP ou « à utiliser avant », format MM/AAAA). Ne donne aucun conseil médical."
)
TEXTE = {"text": {}}
STRUCTURE = {
    "nom": {"description": "Nom commercial du produit, sans le dosage", "required": True, "selector": TEXTE},
    "substances_texte": {"description": "Substances actives écrites sur la boîte, séparées par des virgules", "selector": TEXTE},
    "dosage": {"description": "Dosage écrit sur la boîte, par exemple 500 mg", "selector": TEXTE},
    "forme": {"description": "Forme du produit", "selector": {"select": {"options": stock.FORMES}}},
    "peremption": {"description": "Date de péremption écrite sur la boîte, au format MM/AAAA, sinon vide", "selector": TEXTE},
}


class IAErreur(Exception):
    pass


def _appeler(chemin, corps=None, methode="POST", timeout=20):
    """Requête vers l'API de Home Assistant, par le Supervisor. Réservée au mode application."""
    jeton = os.environ.get("SUPERVISOR_TOKEN")
    if not jeton:
        raise IAErreur("Home Assistant n'est pas connecté")
    donnees = None if corps is None else json.dumps(corps).encode()
    req = urllib.request.Request(f"http://supervisor/core/api{chemin}", data=donnees, method=methode,
                                 headers={"Authorization": f"Bearer {jeton}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as rep:
        return json.loads(rep.read().decode() or "null")


def _noms(produits, nb=10):
    return [p["nom"] for p in produits[:nb]]


def valeurs_capteurs(resume):
    commun = {"icon": "mdi:medical-bag"}
    return {
        "sensor.pharmacie_produits": (resume["produits"], {**commun, "friendly_name": "Pharmacie - Produits", "unit_of_measurement": "produits", "state_class": "measurement"}),
        "sensor.pharmacie_perimes": (len(resume["perimes"]), {**commun, "friendly_name": "Pharmacie - Périmés", "unit_of_measurement": "produits", "state_class": "measurement", "produits": _noms(resume["perimes"])}),
        "sensor.pharmacie_bientot_perimes": (len(resume["bientot"]), {**commun, "friendly_name": "Pharmacie - Bientôt périmés", "unit_of_measurement": "produits", "state_class": "measurement", "produits": _noms(resume["bientot"])}),
        "sensor.pharmacie_a_racheter": (len(resume["epuises"]) + len(resume["courses"]), {**commun, "friendly_name": "Pharmacie - À racheter", "unit_of_measurement": "produits", "state_class": "measurement", "produits": _noms(resume["epuises"]) + [c["libelle"] for c in resume["courses"]][:10]}),
    }


def publier_capteurs(conn):
    """Écrit les capteurs dans HA. Ils disparaissent à son redémarrage : le serveur les réécrit régulièrement."""
    if not os.environ.get("SUPERVISOR_TOKEN"):
        return False
    try:
        for entite, (etat, attributs) in valeurs_capteurs(stock.resume(conn)).items():
            _appeler(f"/states/{entite}", {"state": etat, "attributes": attributs})
        return True
    except (urllib.error.URLError, OSError, ValueError, IAErreur) as e:
        log.warning("Capteurs non publiés : %s", e)
        return False


def _dossier_media():
    chemin = os.environ.get("HA_MEDIA_DIR", "/media")
    return Path(chemin) if Path(chemin).is_dir() else None


def _nettoyer(donnees):
    """Réponse de l'IA ramenée aux champs du formulaire. Le formulaire reste à vérifier avant d'enregistrer."""
    champs = {c: str(donnees.get(c) or "").strip() for c in STRUCTURE}
    champs["peremption"] = stock.normaliser_peremption(champs["peremption"])
    if champs["forme"] not in stock.FORMES:
        champs["forme"] = ""
    champs["substances"] = cat.trouver_substances(champs["substances_texte"]) or cat.trouver_substances(champs["nom"])
    return champs


def lire_boite(photos, timeout=90):
    """photos : images JPEG (octets). Elles ne restent dans le dossier media que le temps de la lecture."""
    dossier = _dossier_media()
    if not dossier or not os.environ.get("SUPERVISOR_TOKEN"):
        raise IAErreur("L'IA de Home Assistant n'est pas disponible ici")
    entites = [e["entity_id"] for e in _appeler("/states", methode="GET")
               if e["entity_id"].startswith("ai_task.") and e["state"] != "unavailable"]
    if not entites:
        raise IAErreur("Aucune IA de type « tâche IA » n'est disponible dans Home Assistant")
    sous_dossier = dossier / SOUS_DOSSIER
    sous_dossier.mkdir(exist_ok=True)
    noms = []
    try:
        for image in photos:
            nom = secrets.token_hex(8) + ".jpg"
            (sous_dossier / nom).write_bytes(image)
            noms.append(nom)
        reponse = _appeler("/services/ai_task/generate_data?return_response", {
            "entity_id": entites[0], "task_name": "Lecture d'une boîte de médicament", "instructions": INSTRUCTIONS,
            "structure": STRUCTURE,
            "attachments": [{"media_content_id": f"media-source://media_source/local/{SOUS_DOSSIER}/{n}",
                             "media_content_type": "image/jpeg"} for n in noms],
        }, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise IAErreur(f"L'IA de Home Assistant a refusé la demande ({e.code})")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise IAErreur(f"Home Assistant injoignable ({getattr(e, 'reason', e)})")
    finally:
        for nom in noms:
            (sous_dossier / nom).unlink(missing_ok=True)
    donnees = (reponse.get("service_response") or {}).get("data")
    if isinstance(donnees, str):
        try:
            donnees = json.loads(donnees)
        except ValueError:
            raise IAErreur("L'IA n'a pas renvoyé de données exploitables")
    if not isinstance(donnees, dict):
        raise IAErreur("Réponse de l'IA inattendue")
    return _nettoyer(donnees)
