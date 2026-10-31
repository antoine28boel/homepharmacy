"""Tests sans dépendance : python -m unittest discover -s tests (depuis pharmacie/)."""

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1] / "pharmacie"))

from app import catalogue as cat  # noqa: E402
from app import ha, server, stock  # noqa: E402


class Catalogue(unittest.TestCase):
    def test_coherent(self):
        self.assertEqual(cat.verifier(), [])

    def test_aucune_posologie(self):
        """La dose vient de la notice : aucun « mg » ni nombre de prises dans le catalogue."""
        texte = json.dumps([cat.SUBSTANCES, cat.MAUX], ensure_ascii=False)
        self.assertNotRegex(texte, r"\d\s?(mg|g|ml)\b")
        self.assertNotRegex(texte, r"\d+\s?(comprimés?|gélules?|fois par jour)")

    def test_marques_et_substances(self):
        self.assertEqual(cat.trouver_substances("Dafalgan Forte"), ["paracetamol"])
        self.assertEqual(cat.trouver_substances("Paracétamol, Pseudoéphédrine"), ["paracetamol", "pseudoephedrine"])
        self.assertEqual(cat.trouver_substances("Nurofen 400"), ["ibuprofene"])
        self.assertEqual(cat.trouver_substances("Bonbon inconnu"), [])

    def test_gel_n_est_pas_un_comprime(self):
        self.assertEqual(cat.trouver_substances("Ibuprofène gel"), ["ains_gel"])

    def test_alias_sans_collision(self):
        vus = {}
        for cle, s in cat.SUBSTANCES.items():
            for a in s["alias"]:
                n = cat.normaliser(a)
                self.assertNotIn(n, vus, f"{a} dans {cle} et {vus.get(n)}")
                vus[n] = cle

    def test_signes_de_gravite_du_mal_de_poitrine(self):
        self.assertTrue(cat.MAUX["estomac"]["urgence"])
        self.assertTrue(cat.MAUX["mal_de_tete"]["urgence"])

    def test_substances_a_risque_jamais_en_premier(self):
        for cle, m in cat.MAUX.items():
            for s in m["principal"]:
                self.assertFalse(cat.SUBSTANCES[s].get("prescription"), f"{cle} propose {s} en premier")


class Dates(unittest.TestCase):
    def test_formats(self):
        for brut, attendu in [("03/2027", "2027-03"), ("EXP 03-27", "2027-03"), ("2027-03", "2027-03"),
                              ("31/03/2027", "2027-03"), ("EXP: 3.2027", "2027-03"), ("12/28", "2028-12")]:
            self.assertEqual(stock.normaliser_peremption(brut), attendu, brut)

    def test_illisible(self):
        for brut in ("", "bientôt", "13/2027", "lot 123456"):
            self.assertEqual(stock.normaliser_peremption(brut), "", brut)

    def test_etats(self):
        p = {"peremption": "2026-10", "quantite": 1, "forme": "", "ouvert_le": ""}
        self.assertEqual(stock.etat_produit(p, date(2026, 10, 31))[0], "bientot")  # valable jusqu'à la fin du mois
        self.assertEqual(stock.etat_produit(p, date(2026, 11, 1))[0], "perime")
        p["peremption"] = "2028-01"
        self.assertEqual(stock.etat_produit(p, date(2026, 10, 31))[0], "ok")
        p["peremption"] = ""
        self.assertEqual(stock.etat_produit(p, date(2026, 10, 31))[0], "inconnu")
        p.update(peremption="2028-01", quantite=0)
        self.assertEqual(stock.etat_produit(p, date(2026, 10, 31))[0], "epuise")
        p.update(quantite=1, forme="collyre", ouvert_le="2026-09-01")
        self.assertEqual(stock.etat_produit(p, date(2026, 10, 31))[0], "ouvert_trop_longtemps")


class Stock(unittest.TestCase):
    def setUp(self):
        self.conn = stock.ouvrir(":memory:")

    def ajouter(self, **d):
        return stock.ajouter(self.conn, {"peremption": "01/2099", **d})

    def test_nom_obligatoire(self):
        with self.assertRaises(stock.Invalide):
            stock.ajouter(self.conn, {"nom": " "})

    def test_date_illisible_refusee(self):
        with self.assertRaises(stock.Invalide):
            stock.ajouter(self.conn, {"nom": "X", "peremption": "bientôt"})

    def test_le_texte_de_la_boite_prime_sur_la_marque(self):
        p = self.ajouter(nom="Dafalgan", substances_texte="Ibuprofène")
        self.assertEqual(p["substances"], ["ibuprofene"])

    def test_perime_ecarte_des_conseils(self):
        self.ajouter(nom="Dafalgan", peremption="01/2020")
        fiche = stock.conseils(self.conn, "mal_de_tete")
        self.assertEqual(fiche["principal"][0]["produits"], [])
        self.assertEqual([p["nom"] for p in fiche["a_ecarter"]], ["Dafalgan"])
        self.assertIn("Paracétamol", fiche["manque"])

    def test_epuise_ecarte(self):
        self.ajouter(nom="Dafalgan", quantite=0)
        self.assertEqual(stock.conseils(self.conn, "mal_de_tete")["principal"][0]["produits"], [])

    def test_disponible(self):
        self.ajouter(nom="Dafalgan")
        fiche = stock.conseils(self.conn, "mal_de_tete")
        self.assertEqual(fiche["principal"][0]["produits"][0]["nom"], "Dafalgan")
        self.assertEqual(fiche["manque"], [])
        self.assertTrue(next(m for m in stock.liste_maux(self.conn) if m["cle"] == "mal_de_tete")["disponible"])

    def test_cumul_paracetamol_signale(self):
        self.ajouter(nom="Dafalgan")
        self.ajouter(nom="Rhume Forte", substances_texte="paracétamol, pseudoéphédrine")
        cumul = stock.conseils(self.conn, "fievre")["cumul"]
        self.assertEqual(cumul[0]["produits"], ["Dafalgan", "Rhume Forte"])

    def test_cumul_anti_inflammatoires_signale(self):
        self.ajouter(nom="Nurofen")
        self.ajouter(nom="Aleve")
        self.assertTrue(stock.conseils(self.conn, "mal_de_dos")["cumul"])

    def test_pas_de_cumul_entre_pansements(self):
        self.ajouter(nom="Pansements A", substances=["pansement"])
        self.ajouter(nom="Pansements B", substances=["pansement"])
        self.assertEqual(stock.conseils(self.conn, "plaie")["cumul"], [])

    def test_antibiotique_jamais_propose(self):
        self.ajouter(nom="Reste", substances_texte="amoxicilline")
        for cle in cat.MAUX:
            fiche = stock.conseils(self.conn, cle)
            for s in fiche["principal"] + fiche["aussi"]:
                self.assertEqual(s["produits"], [], cle)

    def test_association_a_risque_ecartee(self):
        self.ajouter(nom="Rhume Forte", substances_texte="paracétamol, pseudoéphédrine")
        self.ajouter(nom="Dafalgan Codéine", substances_texte="paracétamol, codéine")
        fiche = stock.conseils(self.conn, "fievre")
        self.assertEqual(fiche["principal"][1]["produits"], [])
        self.assertEqual(sorted(p["nom"] for p in fiche["a_ecarter"]), ["Dafalgan Codéine", "Rhume Forte"])
        self.assertIn("Pseudoéphédrine", next(p for p in fiche["a_ecarter"] if p["nom"] == "Rhume Forte")["raison"])
        self.assertFalse(next(m for m in stock.liste_maux(self.conn) if m["cle"] == "mal_de_tete")["disponible"])

    def test_substance_sur_avis_reste_visible_pour_elle_meme(self):
        self.ajouter(nom="Motilium")
        fiche = stock.conseils(self.conn, "nausees")
        self.assertEqual(fiche["aussi"][0]["produits"][0]["nom"], "Motilium")
        self.assertTrue(fiche["aussi"][0]["sur_avis"])

    def test_association_personnelle(self):
        p = self.ajouter(nom="Baume maison", maux_perso=["piqure"])
        self.assertEqual(stock.conseils(self.conn, "piqure")["perso"][0]["id"], p["id"])

    def test_substance_ou_mal_inconnu_refuse(self):
        with self.assertRaises(stock.Invalide):
            self.ajouter(nom="X", substances=["inconnu"])
        with self.assertRaises(stock.Invalide):
            self.ajouter(nom="X", maux_perso=["inconnu"])

    def test_resume_et_capteurs(self):
        self.ajouter(nom="A")
        self.ajouter(nom="B", peremption="01/2020")
        self.ajouter(nom="C", quantite=0)
        stock.ajouter_course(self.conn, "Thermomètre")
        v = ha.valeurs_capteurs(stock.resume(self.conn))
        self.assertEqual(v["sensor.pharmacie_produits"][0], 2)
        self.assertEqual(v["sensor.pharmacie_perimes"][0], 1)
        self.assertEqual(v["sensor.pharmacie_perimes"][1]["produits"], ["B"])
        self.assertEqual(v["sensor.pharmacie_a_racheter"][0], 2)

    def test_essentiels(self):
        self.ajouter(nom="Dafalgan")
        e = {x["cle"]: x["present"] for x in stock.resume(self.conn)["essentiels"]}
        self.assertTrue(e["paracetamol"])
        self.assertFalse(e["thermometre"])


class LectureIA(unittest.TestCase):
    def test_nettoyage(self):
        r = ha._nettoyer({"nom": "Dafalgan", "substances_texte": "Paracétamol", "dosage": "500 mg",
                          "forme": "comprimé", "peremption": "EXP 03/2028"})
        self.assertEqual(r["peremption"], "2028-03")
        self.assertEqual(r["substances"], ["paracetamol"])

    def test_date_ou_forme_inventee_videe(self):
        r = ha._nettoyer({"nom": "X", "forme": "potion", "peremption": "bientôt"})
        self.assertEqual((r["forme"], r["peremption"]), ("", ""))


class API(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = server.Application(":memory:")
        cls.serveur = ThreadingHTTPServer(("127.0.0.1", 0), server.fabriquer_gestionnaire(cls.app))
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.serveur.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()

    def appel(self, chemin, methode="GET", corps=None):
        donnees = None if corps is None else json.dumps(corps).encode()
        req = urllib.request.Request(self.base + chemin, data=donnees, method=methode)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_parcours(self):
        code, p = self.appel("/api/produits", "POST", {"nom": "Nurofen", "peremption": "03/2099"})
        self.assertEqual((code, p["substances"], p["peremption"]), (201, ["ibuprofene"], "2099-03"))
        code, p = self.appel(f"/api/produits/{p['id']}", "PUT", {"quantite": 0})
        self.assertEqual((code, p["etat"]), (200, "epuise"))
        self.assertEqual(self.appel(f"/api/produits/{p['id']}", "DELETE")[0], 200)
        self.assertEqual(self.appel(f"/api/produits/{p['id']}")[0], 404)

    def test_erreurs_lisibles(self):
        self.assertEqual(self.appel("/api/produits", "POST", {"nom": ""})[0], 400)
        self.assertEqual(self.appel("/api/maux/inconnu")[0], 404)
        self.assertEqual(self.appel("/api/produits/9999", "PUT", {"nom": "X"})[0], 404)

    def test_pas_de_sortie_du_dossier(self):
        req = urllib.request.Request(self.base + "/../../server.py")
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        self.assertEqual(e.exception.code, 404)

    def test_seul_l_ingress_passe_dans_home_assistant(self):
        with mock.patch.dict("os.environ", {"SUPERVISOR_TOKEN": "x"}):
            self.assertEqual(self.appel("/api/produits")[0], 403)
            self.assertEqual(self.appel("/api/health")[0], 200)

    def test_photo_invalide(self):
        self.assertEqual(self.appel("/api/lire-boite", "POST", {"photos": ["pas une image"]})[0], 400)
        self.assertEqual(self.appel("/api/lire-boite", "POST", {"photos": []})[0], 400)


if __name__ == "__main__":
    unittest.main()
