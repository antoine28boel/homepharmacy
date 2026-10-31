# Pharmacie

Application Home Assistant pour l'armoire à pharmacie d'une maison : ce qu'on a, ce qui périme, et quoi utiliser selon
les petits maux des adultes.

- **J'ai mal** : choisissez un mal. La fiche indique d'abord quand appeler le 112 ou consulter, puis les gestes utiles,
  et enfin les produits de votre armoire. Elle signale les doublons à ne pas cumuler et les produits périmés.
- **Armoire** : photographiez une boîte, l'IA de Home Assistant lit le nom, les substances et la date. Vous vérifiez
  avant d'enregistrer.
- **À racheter** : périmés, épuisés, liste de courses et trousse de base.
- **Capteurs** : `sensor.pharmacie_produits`, `sensor.pharmacie_perimes`, `sensor.pharmacie_bientot_perimes`,
  `sensor.pharmacie_a_racheter`.

**Ce n'est pas un avis médical.** Les conseils sont prévus pour des adultes, ne donnent aucune dose et n'ont pas été
relus par un professionnel de santé (voir [SOURCES.md](SOURCES.md)). Numéros prévus pour la Belgique.

## Installation

Ajoutez `https://github.com/antoine28boel/homepharmacy` aux dépôts d'applications de Home Assistant, puis installez
**Pharmacie**. La lecture des photos demande une intégration d'IA avec une « tâche IA » (AI Task) : les photos sont
envoyées à ce service, puis effacées du dossier media. Sans IA, la fiche se remplit à la main.

## Développement

```bash
python -m unittest discover -s tests
PHARMACIE_BASE=./essai.db PHARMACIE_PORT=8099 PYTHONPATH=pharmacie python -m app
```

Aucune dépendance en dehors de la bibliothèque standard de Python.
