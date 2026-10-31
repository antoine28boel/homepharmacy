"""Serveur HTTP de l'application, sans dépendance : API JSON et fichiers de l'interface."""

import base64
import json
import logging
import mimetypes
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import catalogue as cat
from . import ha, stock

log = logging.getLogger("pharmacie")
STATIQUE = Path(__file__).parent / "static"
INGRESS = "172.30.32.2"  # seule adresse qui peut parler à l'application dans Home Assistant
CORPS_MAX = 30_000_000
PHOTOS_MAX = 3
PUBLICATION_SECONDES = 300


class Application:
    """État partagé : la base (sqlite3 sérialisé par un verrou) et le signal de publication des capteurs."""

    def __init__(self, chemin_base):
        self.conn = stock.ouvrir(chemin_base)
        self.verrou = threading.Lock()
        self.changement = threading.Event()

    def publier_en_boucle(self):
        while True:
            self.changement.clear()
            ha.publier_capteurs(self.conn)
            self.changement.wait(PUBLICATION_SECONDES)


def fabriquer_gestionnaire(app):
    class Gestionnaire(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "Pharmacie"

        def log_message(self, *args):
            log.debug(args[0], *args[1:])

        def _envoyer(self, code, corps, type_contenu="application/json; charset=utf-8", entetes=()):
            self.send_response(code)
            self.send_header("Content-Type", type_contenu)
            self.send_header("Content-Length", str(len(corps)))
            self.send_header("Cache-Control", "no-cache")
            for nom, valeur in entetes:
                self.send_header(nom, valeur)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(corps)

        def _json(self, donnees, code=200):
            self._envoyer(code, json.dumps(donnees, ensure_ascii=False).encode("utf-8"))

        def _erreur(self, code, message):
            self._json({"erreur": message}, code)

        def _corps(self):
            longueur = int(self.headers.get("Content-Length") or 0)
            if longueur > CORPS_MAX:
                self.close_connection = True
                raise stock.Invalide("Envoi trop volumineux")
            brut = self.rfile.read(longueur) if longueur else b"{}"
            try:
                donnees = json.loads(brut.decode("utf-8"))
            except ValueError:
                raise stock.Invalide("Requête illisible")
            if not isinstance(donnees, dict):
                raise stock.Invalide("Requête illisible")
            return donnees

        def _autorise(self):
            # Hors de Home Assistant (essais en local), pas de filtre ; dedans, seul l'ingress passe.
            if not os.environ.get("SUPERVISOR_TOKEN") or self.path.startswith("/api/health"):
                return True
            return self.client_address[0] == INGRESS

        def _traiter(self):
            if not self._autorise():
                return self._erreur(403, "Accès réservé à Home Assistant")
            try:
                chemin = self.path.split("?", 1)[0]
                if chemin.startswith("/api/"):
                    return self._api(chemin[5:])
                if self.command not in ("GET", "HEAD"):
                    return self._erreur(405, "Méthode non autorisée")
                return self._fichier(chemin)
            except stock.Invalide as e:
                return self._erreur(400, str(e))
            except ha.IAErreur as e:
                return self._erreur(503, str(e))
            except BrokenPipeError:
                return None
            except Exception:
                log.exception("Erreur sur %s %s", self.command, self.path)
                return self._erreur(500, "Erreur interne")

        do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = _traiter

        def _fichier(self, chemin):
            nom = chemin.lstrip("/") or "index.html"
            cible = (STATIQUE / nom).resolve()
            if not cible.is_relative_to(STATIQUE.resolve()) or not cible.is_file():
                return self._erreur(404, "Introuvable")
            type_contenu = mimetypes.guess_type(cible.name)[0] or "application/octet-stream"
            if type_contenu.startswith("text/") or type_contenu.endswith("javascript"):
                type_contenu += "; charset=utf-8"
            return self._envoyer(200, cible.read_bytes(), type_contenu)

        def _ecrit(self, reponse, code=200):
            app.changement.set()
            return self._json(reponse, code)

        def _api(self, r):
            m = self.command
            conn = app.conn
            if r == "health":
                return self._json({"ok": True})
            if r == "maux" and m == "GET":
                return self._json({"maux": stock.liste_maux(conn), "groupes": cat.GROUPES,
                                   "urgence": cat.URGENCE_GENERALE, "garde": cat.PHARMACIE_DE_GARDE})
            trouve = re.fullmatch(r"maux/([a-z_]+)", r)
            if trouve and m == "GET":
                fiche = stock.conseils(conn, trouve[1])
                return self._json(fiche) if fiche else self._erreur(404, "Mal inconnu")
            if r == "substances" and m == "GET":
                return self._json({"substances": [{"cle": k, "nom": s["nom"]} for k, s in cat.SUBSTANCES.items()],
                                   "formes": stock.FORMES,
                                   "ia": bool(os.environ.get("SUPERVISOR_TOKEN"))})
            if r == "resume" and m == "GET":
                return self._json(stock.resume(conn))
            if r == "export.json" and m == "GET":
                return self._json(stock.exporter(conn))
            if r == "produits":
                if m == "GET":
                    return self._json(stock.lister(conn))
                if m == "POST":
                    corps = self._corps()
                    with app.verrou:
                        return self._ecrit(stock.ajouter(conn, corps), 201)
            trouve = re.fullmatch(r"produits/(\d+)", r)
            if trouve:
                pid = int(trouve[1])
                if m == "GET":
                    p = stock.lire(conn, pid)
                    return self._json(p) if p else self._erreur(404, "Produit introuvable")
                if m == "PUT":
                    corps = self._corps()
                    with app.verrou:
                        p = stock.modifier(conn, pid, corps)
                    return self._ecrit(p) if p else self._erreur(404, "Produit introuvable")
                if m == "DELETE":
                    with app.verrou:
                        fait = stock.supprimer(conn, pid)
                    return self._ecrit({"ok": True}) if fait else self._erreur(404, "Produit introuvable")
            if r == "courses":
                if m == "GET":
                    return self._json(stock.courses(conn))
                if m == "POST":
                    corps = self._corps()
                    with app.verrou:
                        return self._ecrit(stock.ajouter_course(conn, corps.get("libelle")), 201)
            trouve = re.fullmatch(r"courses/(\d+)", r)
            if trouve and m == "DELETE":
                with app.verrou:
                    fait = stock.supprimer_course(conn, int(trouve[1]))
                return self._ecrit({"ok": True}) if fait else self._erreur(404, "Article introuvable")
            if r == "lire-boite" and m == "POST":
                return self._json(ha.lire_boite(_photos(self._corps())))
            return self._erreur(404, "Introuvable")

    return Gestionnaire


def _photos(corps):
    """Décode les photos reçues en data URL (l'interface les réduit et les convertit en JPEG)."""
    photos = corps.get("photos")
    if not isinstance(photos, list) or not 1 <= len(photos) <= PHOTOS_MAX:
        raise stock.Invalide(f"Envoyez entre 1 et {PHOTOS_MAX} photos")
    sortie = []
    for p in photos:
        if not isinstance(p, str) or not p.startswith("data:image/jpeg;base64,"):
            raise stock.Invalide("Photo invalide")
        try:
            sortie.append(base64.b64decode(p.split(",", 1)[1], validate=True))
        except ValueError:
            raise stock.Invalide("Photo invalide")
    return sortie


def demarrer(chemin_base, hote="0.0.0.0", port=8099):
    app = Application(chemin_base)
    serveur = ThreadingHTTPServer((hote, port), fabriquer_gestionnaire(app))
    threading.Thread(target=app.publier_en_boucle, daemon=True).start()
    log.info("Pharmacie à l'écoute sur le port %s", port)
    serveur.serve_forever()
