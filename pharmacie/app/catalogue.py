"""Catalogue de conseils pour adultes : substances, maux, et lien entre les deux.

Choix de sécurité :
- aucune posologie ici : la dose vient toujours de la notice du produit ;
- rien n'est généré par une IA au moment de la consultation : ce fichier est relu et testé ;
- chaque mal indique quand consulter ; ces signes sont affichés avant les produits.
Sources : voir SOURCES.md.
"""

import re
import unicodedata

# classe : deux produits de la même classe ne se cumulent pas sans avis.
# type : "medicament" ou "soin" (pansement, thermomètre… : pas de précaution de cumul).
SUBSTANCES = {
    # Douleur et fièvre
    "paracetamol": {
        "nom": "Paracétamol", "classe": "paracetamol", "role": "Douleur et fièvre, à essayer en premier",
        "alias": ["paracetamol", "acetaminophene", "acetaminophen", "dafalgan", "perdolan", "panadol", "algostase", "lemsip"],
        "precautions": ["Beaucoup de produits contre le rhume en contiennent déjà : vérifiez avant de cumuler.",
                        "Une dose trop élevée abîme le foie : respectez strictement la notice.",
                        "Demandez conseil en cas de maladie du foie ou de consommation régulière d'alcool."],
    },
    "ibuprofene": {
        "nom": "Ibuprofène", "classe": "ains", "role": "Anti-inflammatoire contre la douleur et la fièvre",
        "alias": ["ibuprofene", "ibuprofen", "dexibuprofene", "nurofen", "brufen", "spidifen", "ibumed", "perdophen"],
        "duree": "En automédication : 3 jours pour la fièvre, 5 jours pour la douleur, sauf avis médical.",
        "precautions": ["Ne jamais associer à un autre anti-inflammatoire ni à l'aspirine.",
                        "À éviter sans avis en cas d'ulcère, de maladie des reins ou du cœur, d'anticoagulant, "
                        "ou d'asthme déclenché par l'aspirine.",
                        "À prendre de préférence pendant le repas."],
    },
    "naproxene": {
        "nom": "Naproxène", "classe": "ains", "role": "Anti-inflammatoire contre la douleur",
        "alias": ["naproxene", "naproxen", "aleve", "apranax", "naprosyn"],
        "duree": "Courte durée seulement, selon la notice.",
        "precautions": ["Ne jamais associer à un autre anti-inflammatoire ni à l'aspirine.",
                        "À éviter sans avis en cas d'ulcère, de maladie des reins ou du cœur, ou d'anticoagulant."],
    },
    "aspirine": {
        "nom": "Aspirine", "classe": "ains", "role": "Douleur et fièvre, rarement le premier choix",
        "alias": ["aspirine", "aspirin", "acide acetylsalicylique", "aspro", "dispril"],
        "precautions": ["Augmente le risque de saignement : à éviter avant une intervention ou un soin dentaire.",
                        "Ne jamais associer à un anti-inflammatoire ni à un anticoagulant sans avis.",
                        "Si de l'aspirine vous est prescrite pour le cœur, n'arrêtez pas et n'ajoutez rien sans avis."],
    },
    "codeine": {
        "nom": "Codéine", "classe": "opioide", "role": "Antidouleur sur prescription",
        "alias": ["codeine"],
        "prescription": True,
        "precautions": ["À utiliser seulement sur avis médical : somnolence, constipation, risque de dépendance."],
    },
    "ains_gel": {
        "nom": "Anti-inflammatoire en gel (diclofénac…)", "classe": "ains_local", "role": "Contusion, entorse, douleur locale",
        "alias": ["diclofenac", "voltaren", "flector", "ketoprofene gel", "piroxicam gel", "ibuprofene gel"],
        "precautions": ["Sur peau intacte seulement, jamais sur une plaie ni près des yeux.",
                        "Évitez le soleil sur la zone traitée, selon la notice."],
    },
    "pastille_ains": {
        "nom": "Pastille ou spray anti-inflammatoire pour la gorge", "classe": "ains_local", "role": "Mal de gorge",
        "alias": ["flurbiprofene", "strefen", "benzydamine", "tantum verde"],
        "precautions": ["Le flurbiprofène est un anti-inflammatoire : prudence si vous en prenez déjà un autre."],
    },
    # Rhume, gorge, toux, allergie
    "serum_physio": {
        "nom": "Sérum physiologique ou eau de mer", "classe": "lavage_nez", "type": "soin", "role": "Laver et dégager le nez",
        "alias": ["serum physiologique", "chlorure de sodium", "sterimar", "physiomer", "rhinomer", "eau de mer"],
        "precautions": [],
    },
    "decongestionnant": {
        "nom": "Spray décongestionnant nasal", "classe": "decongestionnant", "role": "Nez très bouché",
        "alias": ["xylometazoline", "oxymetazoline", "otrivine", "otrivin", "nesivine", "vicks sinex", "sinex"],
        "duree": "5 jours maximum : au-delà, le nez se rebouche et la rhinite peut devenir chronique.",
        "precautions": ["Demandez conseil en cas d'hypertension ou de problème cardiaque.",
                        "Ne pas associer à un décongestionnant en comprimé (pseudoéphédrine)."],
    },
    "pseudoephedrine": {
        "nom": "Pseudoéphédrine (décongestionnant en comprimé)", "classe": "decongestionnant", "role": "Déconseillé pour un simple rhume",
        "alias": ["pseudoephedrine", "sudafed", "actifed", "rhinofebryl"],
        "deconseille": True,
        "precautions": ["Risque rare mais grave pour le cerveau et les vaisseaux. Interdite en cas d'hypertension "
                        "sévère ou non contrôlée et de maladie grave des reins.",
                        "Arrêtez et appelez les secours en cas de mal de tête soudain et violent, de confusion "
                        "ou de troubles de la vue."],
    },
    "pastille_gorge": {
        "nom": "Pastille pour la gorge", "classe": "pastille", "role": "Soulager le mal de gorge",
        "alias": ["strepsils", "mebucaine", "lysopaine", "neo-sabenyl", "isla", "benzocaine", "lidocaine pastille",
                  "cetylpyridinium", "amylmetacresol", "tyrothricine"],
        "precautions": ["Les pastilles anesthésiantes peuvent gêner la déglutition : évitez de manger juste après."],
    },
    "antitussif": {
        "nom": "Sirop contre la toux sèche (dextrométhorphane)", "classe": "antitussif", "role": "Toux sèche qui empêche de dormir",
        "alias": ["dextromethorphane", "dextromethorphan", "toularynx", "bronchosedal", "vicks antitussif"],
        "precautions": ["Pas pour une toux grasse : elle sert à évacuer les sécrétions.",
                        "Demandez conseil si vous prenez un antidépresseur.",
                        "Peut donner de la somnolence."],
    },
    "mucolytique": {
        "nom": "Fluidifiant de la toux grasse (acétylcystéine…)", "classe": "mucolytique", "role": "Toux grasse, efficacité modeste",
        "alias": ["acetylcysteine", "carbocisteine", "ambroxol", "bromhexine", "lysomucil", "fluimucil", "bisolvon"],
        "precautions": ["Demandez conseil en cas d'ulcère de l'estomac ou d'asthme."],
    },
    "antihistaminique": {
        "nom": "Antihistaminique (cétirizine, loratadine…)", "classe": "antihistaminique", "role": "Allergie, démangeaisons, urticaire légère",
        "alias": ["cetirizine", "levocetirizine", "loratadine", "desloratadine", "fexofenadine", "bilastine", "ebastine",
                  "zyrtec", "xyzall", "claritine", "aerius", "telfast", "bellozal"],
        "precautions": ["Peut endormir : soyez prudent au volant et avec l'alcool, surtout la première fois."],
    },
    "corticoide_nasal": {
        "nom": "Spray nasal à la cortisone", "classe": "corticoide_nasal", "role": "Rhinite allergique installée",
        "alias": ["fluticasone", "mometasone", "budesonide nasal", "beclometasone nasal", "flixonase", "nasonex", "rhinocort"],
        "precautions": ["L'effet n'est pas immédiat : il faut quelques jours d'usage régulier.",
                        "Demandez l'avis du médecin ou du pharmacien si les symptômes persistent."],
    },
    "collyre_allergie": {
        "nom": "Collyre contre l'allergie", "classe": "collyre", "role": "Yeux qui piquent à cause d'une allergie",
        "alias": ["cromoglicate", "olopatadine", "ketotifene", "azelastine collyre", "opatanol", "zaditen"],
        "precautions": ["Retirez les lentilles avant l'application."],
    },
    "larmes": {
        "nom": "Larmes artificielles", "classe": "collyre", "role": "Yeux secs ou irrités",
        "alias": ["larmes artificielles", "hyaluronate", "acide hyaluronique collyre", "carmellose", "systane", "hylo", "vismed", "artelac"],
        "precautions": ["Un flacon ouvert se garde peu de temps : voyez la durée sur la notice."],
    },
    # Ventre
    "sro": {
        "nom": "Solution de réhydratation orale", "classe": "sro", "role": "Remplacer l'eau et les sels perdus",
        "alias": ["rehydratation", "normolytoral", "oralsan", "orolyte", "ors", "sro"],
        "precautions": ["Préparez-la exactement comme indiqué, sans ajouter de sucre."],
    },
    "loperamide": {
        "nom": "Lopéramide", "classe": "antidiarrheique", "role": "Calmer une diarrhée qui gêne, sans remplacer l'hydratation",
        "alias": ["loperamide", "imodium", "diarstop"],
        "duree": "2 jours maximum. Sans amélioration, consultez.",
        "precautions": ["Pas en cas de sang dans les selles ou de forte fièvre.",
                        "Pas en cas de diarrhée survenue sous antibiotiques.",
                        "Ne dépassez jamais la dose de la notice : surdosage dangereux pour le cœur."],
    },
    "macrogol": {
        "nom": "Macrogol", "classe": "laxatif_doux", "role": "Constipation, laxatif doux",
        "alias": ["macrogol", "movicol", "forlax", "transipeg", "laxido"],
        "precautions": ["Buvez suffisamment. L'effet peut prendre un à deux jours."],
    },
    "lactulose": {
        "nom": "Lactulose", "classe": "laxatif_doux", "role": "Constipation, laxatif doux",
        "alias": ["lactulose", "duphalac", "bifiteral"],
        "precautions": ["Peut donner des gaz au début."],
    },
    "fibres": {
        "nom": "Fibres (psyllium, ispaghul)", "classe": "fibres", "role": "Constipation légère",
        "alias": ["psyllium", "ispaghul", "ispaghula", "spagulax", "metamucil"],
        "precautions": ["Toujours avec un grand verre d'eau, sinon risque de blocage."],
    },
    "laxatif_stimulant": {
        "nom": "Laxatif stimulant (bisacodyl, séné)", "classe": "laxatif_stimulant", "role": "Dépannage ponctuel",
        "alias": ["bisacodyl", "dulcolax", "sene", "sennosides", "picosulfate", "agiolax", "fucus"],
        "duree": "Ponctuellement, quelques jours au plus.",
        "precautions": ["Un usage prolongé entretient la constipation."],
    },
    "glycerine": {
        "nom": "Suppositoire à la glycérine", "classe": "laxatif_local", "role": "Constipation basse, effet rapide",
        "alias": ["glycerine", "glycerol"],
        "precautions": [],
    },
    "antiacide": {
        "nom": "Antiacide ou alginate (Gaviscon, Rennie…)", "classe": "antiacide", "role": "Brûlures d'estomac occasionnelles",
        "alias": ["gaviscon", "rennie", "maalox", "riopan", "alginate", "hydrotalcite", "magaldrate", "algeldrate", "carbonate de calcium"],
        "precautions": ["Peut gêner l'absorption d'autres médicaments : espacez les prises, selon la notice."],
    },
    "ipp": {
        "nom": "Inhibiteur de la pompe à protons (oméprazole…)", "classe": "ipp", "role": "Brûlures d'estomac qui reviennent",
        "alias": ["omeprazole", "pantoprazole", "esomeprazole", "lansoprazole", "rabeprazole", "pantozol", "losec", "nexium"],
        "duree": "En automédication, courte durée. Sans amélioration après 2 semaines, consultez.",
        "precautions": ["Ne soulage pas tout de suite : pour une crise ponctuelle, préférez un antiacide."],
    },
    "antispasmodique": {
        "nom": "Antispasmodique (butylscopolamine…)", "classe": "antispasmodique", "role": "Crampes du ventre",
        "alias": ["butylscopolamine", "buscopan", "mebeverine", "duspatalin", "phloroglucinol", "spasfon"],
        "precautions": ["Demandez conseil en cas de glaucome ou de difficulté à uriner."],
    },
    "simeticone": {
        "nom": "Siméticone", "classe": "simeticone", "role": "Ballonnements et gaz",
        "alias": ["simeticone", "dimeticone", "flatulex", "imogas"],
        "precautions": [],
    },
    "mal_transport": {
        "nom": "Contre le mal des transports (méclozine…)", "classe": "mal_transport", "role": "À prendre avant le trajet",
        "alias": ["meclozine", "dimenhydrinate", "cinnarizine", "agyrax", "touristil", "vomex", "stugeron"],
        "precautions": ["Provoque souvent de la somnolence : ne conduisez pas et évitez l'alcool."],
    },
    "domperidone": {
        "nom": "Dompéridone", "classe": "antinauseeux", "role": "Nausées, seulement sur avis",
        "alias": ["domperidone", "motilium"],
        "prescription": True,
        "precautions": ["Risque pour le rythme cardiaque : seulement sur avis médical, à la dose la plus faible et sur une courte durée."],
    },
    "hemorroides": {
        "nom": "Crème ou suppositoire contre les hémorroïdes", "classe": "hemorroides", "role": "Soulager douleur et démangeaisons",
        "alias": ["hemorroides", "preparation h", "sperti", "anusol", "procto-glyvenol", "proctolog", "tribenoside"],
        "duree": "Quelques jours : sans amélioration après une semaine, consultez.",
        "precautions": [],
    },
    # Peau et petits soins
    "antiseptique": {
        "nom": "Antiseptique (chlorhexidine, iode)", "classe": "antiseptique", "role": "Désinfecter une petite plaie",
        "alias": ["chlorhexidine", "hibidil", "cedium", "hibitane", "povidone", "isobetadine", "iso-betadine", "betadine", "octenidine", "octenisept"],
        "precautions": ["Pas d'iode en cas d'allergie à l'iode ou de maladie de la thyroïde, sans avis.",
                        "N'associez pas plusieurs antiseptiques."],
    },
    "pansement": {
        "nom": "Pansements et compresses", "classe": "pansement", "type": "soin", "role": "Protéger une plaie",
        "alias": ["pansement", "compresse", "sparadrap", "steri-strip", "bande", "hansaplast", "bandage"],
        "precautions": [],
    },
    "pansement_ampoule": {
        "nom": "Pansement pour ampoules", "classe": "pansement_ampoule", "type": "soin", "role": "Protéger une ampoule",
        "alias": ["compeed", "pansement ampoule", "hydrocolloide"],
        "precautions": [],
    },
    "thermometre": {
        "nom": "Thermomètre", "classe": "thermometre", "type": "soin", "role": "Mesurer la fièvre",
        "alias": ["thermometre"],
        "precautions": [],
    },
    "froid": {
        "nom": "Poche de froid", "classe": "froid", "type": "soin", "role": "Contusion, entorse, piqûre",
        "alias": ["poche de froid", "cold pack", "cold hot", "poche froide"],
        "precautions": ["Jamais directement sur la peau : enveloppez-la dans un linge."],
    },
    "tire_tique": {
        "nom": "Tire-tique", "classe": "tire_tique", "type": "soin", "role": "Retirer une tique sans la presser",
        "alias": ["tire-tique", "tire tique", "pince a tique", "tick"],
        "precautions": [],
    },
    "soin_brulure": {
        "nom": "Crème ou gel pour brûlure légère", "classe": "soin_brulure", "role": "Brûlure légère ou coup de soleil, une fois refroidis",
        "alias": ["biafine", "trolamine", "flamigel", "burnshield", "brulure", "aloe vera", "apres-soleil", "apres soleil"],
        "precautions": ["Pas sur une plaie ouverte ni sur une cloque percée."],
    },
    "antihistaminique_gel": {
        "nom": "Gel contre les démangeaisons", "classe": "gel_demangeaisons", "role": "Piqûres d'insectes",
        "alias": ["dimetindene", "fenistil", "systral", "apaisyl", "calamine", "mepyramine"],
        "precautions": ["Évitez le soleil sur la zone traitée, selon la notice."],
    },
    "hydrocortisone": {
        "nom": "Crème à l'hydrocortisone", "classe": "corticoide_peau", "role": "Démangeaison et rougeur locale",
        "alias": ["hydrocortisone", "cremicort"],
        "duree": "Quelques jours sur une petite surface. Sans amélioration après une semaine, consultez.",
        "precautions": ["Pas sur le visage ni sur une peau infectée ou abîmée sans avis."],
    },
    "antiherpes": {
        "nom": "Crème contre le bouton de fièvre (aciclovir)", "classe": "antiherpes", "role": "Dès les premiers picotements",
        "alias": ["aciclovir", "acyclovir", "zovirax", "penciclovir", "compeed bouton"],
        "precautions": ["Lavez-vous les mains après l'application et ne touchez pas vos yeux."],
    },
    "antifongique": {
        "nom": "Crème antifongique (terbinafine, clotrimazole…)", "classe": "antifongique", "role": "Mycose de la peau ou des pieds",
        "alias": ["terbinafine", "clotrimazole", "miconazole", "econazole", "ketoconazole", "lamisil", "canesten", "daktarin", "pevaryl", "nizoral"],
        "duree": "Continuez la durée complète de la notice, même si cela va mieux.",
        "precautions": [],
    },
    "antifongique_gyneco": {
        "nom": "Ovule ou crème contre la mycose vaginale", "classe": "antifongique_gyneco", "role": "Si le diagnostic a déjà été posé",
        "alias": ["gyno-daktarin", "gyno-canesten", "gyno-pevaryl", "ovule", "fenticonazole", "gynomyk"],
        "precautions": ["Ne traitez seule que si le médecin a déjà diagnostiqué ce problème par le passé."],
    },
    "gel_buccal": {
        "nom": "Gel ou bain de bouche pour aphtes", "classe": "gel_buccal", "role": "Soulager les aphtes",
        "alias": ["pyralvex", "pansoral", "aftab", "aloclair", "corsodyl", "bain de bouche", "eludril", "mucosol"],
        "precautions": ["Un bain de bouche à la chlorhexidine ne s'utilise que peu de temps : il peut colorer les dents."],
    },
    # Sommeil
    "melatonine": {
        "nom": "Mélatonine", "classe": "sommeil", "role": "Décalage horaire, endormissement difficile",
        "alias": ["melatonine", "circadin", "arkorelax"],
        "duree": "Courte durée.",
        "precautions": ["Demandez conseil si vous prenez un traitement régulier ou un anticoagulant."],
    },
    "valeriane": {
        "nom": "Valériane", "classe": "sommeil", "role": "Nervosité et sommeil léger, efficacité modeste",
        "alias": ["valeriane", "dormiplant", "biocalm"],
        "precautions": ["Peut donner de la somnolence : prudence au volant."],
    },
    # Reconnus uniquement pour prévenir : jamais proposés pour un mal.
    "antibiotique": {
        "nom": "Antibiotique", "classe": "antibiotique", "role": "Uniquement sur prescription",
        "alias": ["amoxicilline", "augmentin", "azithromycine", "clarithromycine", "doxycycline", "ciprofloxacine",
                  "nitrofurantoine", "fosfomycine", "levofloxacine", "clamoxyl", "flemoxin", "zitromax", "monuril"],
        "prescription": True,
        "precautions": ["Ne jamais prendre sans prescription, ni reprendre un reste : rapportez-le à la pharmacie."],
    },
}

GROUPES = ["Tête et douleurs", "Nez, gorge, toux", "Ventre", "Peau et petits accidents", "Yeux, bouche, oreilles", "Intime", "Sommeil"]

# principal : à essayer d'abord, dans l'ordre. aussi : autres possibilités.
# urgence : appeler le 112. consulter : voir un médecin ou appeler le 1733 hors des heures de cabinet.
MAUX = {
    "mal_de_tete": {
        "nom": "Mal de tête", "groupe": "Tête et douleurs", "mots": ["migraine", "cephalee", "tete"],
        "principal": ["paracetamol"], "aussi": ["ibuprofene", "naproxene", "aspirine"],
        "gestes": ["Buvez de l'eau et reposez-vous au calme, dans la pénombre.", "Une pause d'écran et un peu d'air frais aident souvent."],
        "urgence": ["Mal de tête soudain et très violent, le pire de votre vie.",
                    "Associé à une difficulté à parler, une faiblesse d'un côté, une confusion ou un trouble de la vue.",
                    "Avec fièvre et nuque raide, ou taches violacées sur la peau."],
        "consulter": ["Après un choc à la tête.", "Il dure plus de 3 jours ou s'aggrave.",
                      "Vous prenez des antidouleurs plus de 10 jours par mois : ils peuvent eux-mêmes entretenir les maux de tête."],
    },
    "fievre": {
        "nom": "Fièvre", "groupe": "Tête et douleurs", "mots": ["temperature", "frissons", "grippe", "etat grippal", "covid", "courbatures"],
        "principal": ["thermometre", "paracetamol"], "aussi": ["ibuprofene"],
        "gestes": ["Buvez régulièrement et reposez-vous, sans trop vous couvrir.",
                   "Une fièvre bien supportée n'a pas forcément besoin d'être traitée."],
        "urgence": ["Taches violacées sur la peau qui ne disparaissent pas à la pression.",
                    "Nuque raide, confusion, difficulté à respirer."],
        "consulter": ["Elle dure plus de 3 jours ou dépasse 40 °C.", "Au retour d'un voyage à l'étranger.",
                      "Vous avez une maladie chronique, une baisse d'immunité, ou vous êtes enceinte."],
    },
    "douleurs": {
        "nom": "Courbatures, douleurs musculaires", "groupe": "Tête et douleurs", "mots": ["muscle", "articulation", "contracture", "torticolis", "crampe"],
        "principal": ["paracetamol"], "aussi": ["ains_gel", "ibuprofene", "naproxene"],
        "gestes": ["Bougez doucement, sans forcer.", "La chaleur détend un muscle contracté."],
        "urgence": ["Douleur dans la poitrine, le bras gauche ou la mâchoire, surtout avec essoufflement ou sueurs."],
        "consulter": ["Articulation gonflée, rouge et chaude.", "Douleur qui dure plus d'une semaine."],
    },
    "mal_de_dos": {
        "nom": "Mal de dos", "groupe": "Tête et douleurs", "mots": ["lombalgie", "lumbago", "reins", "sciatique"],
        "principal": ["paracetamol"], "aussi": ["ains_gel", "ibuprofene", "naproxene"],
        "gestes": ["Restez actif autant que possible : le repos prolongé au lit ralentit la guérison.", "La chaleur peut soulager."],
        "urgence": ["Perte de contrôle des urines ou des selles, ou perte de sensibilité entre les jambes.",
                    "Faiblesse soudaine d'une jambe."],
        "consulter": ["Après une chute ou un accident.", "Avec de la fièvre ou un amaigrissement inexpliqué.",
                      "Douleur qui descend dans la jambe, ou pas d'amélioration après une semaine."],
    },
    "entorse": {
        "nom": "Entorse, coup, bleu", "groupe": "Tête et douleurs", "mots": ["contusion", "cheville", "hematome", "foulure", "choc"],
        "principal": ["froid", "paracetamol"], "aussi": ["ains_gel", "pansement"],
        "gestes": ["Mettez au repos, appliquez du froid enveloppé dans un linge, puis surélevez le membre."],
        "consulter": ["Impossible de faire quatre pas ou de prendre appui.", "Déformation, gros gonflement, douleur vive sur un os.",
                      "Coup à la tête, à la poitrine ou au ventre qui inquiète."],
    },
    "regles": {
        "nom": "Règles douloureuses", "groupe": "Intime", "mots": ["dysmenorrhee", "menstruation", "crampes"],
        "principal": ["ibuprofene", "naproxene"], "aussi": ["paracetamol", "antispasmodique"],
        "gestes": ["Une bouillotte sur le ventre soulage souvent."],
        "urgence": ["Douleur violente d'un côté du ventre avec malaise, ou possibilité de grossesse avec saignement inhabituel."],
        "consulter": ["Douleurs qui empêchent les activités habituelles chaque mois, ou qui s'aggravent.", "Saignements très abondants."],
    },
    "rhume": {
        "nom": "Rhume, nez bouché", "groupe": "Nez, gorge, toux", "mots": ["nez", "sinus", "sinusite", "congestion", "nez qui coule"],
        "principal": ["serum_physio"], "aussi": ["decongestionnant", "paracetamol"],
        "gestes": ["Lavez le nez plusieurs fois par jour.", "Buvez bien et gardez la tête surélevée la nuit.",
                   "Un rhume guérit seul en une semaine environ : les antibiotiques n'y font rien."],
        "consulter": ["Plus de 10 jours sans amélioration.", "Forte douleur au visage avec fièvre, ou qui reprend après une amélioration."],
    },
    "gorge": {
        "nom": "Mal de gorge", "groupe": "Nez, gorge, toux", "mots": ["angine", "pharyngite", "avaler"],
        "principal": ["paracetamol", "pastille_gorge"], "aussi": ["pastille_ains", "ibuprofene"],
        "gestes": ["Buvez des boissons tièdes, éventuellement avec du miel.", "Évitez le tabac et l'air trop sec."],
        "urgence": ["Difficulté à respirer, ou impossible d'avaler sa salive."],
        "consulter": ["Fièvre élevée sans toux ni rhume, ou ganglions gonflés et douloureux.",
                      "Pas d'amélioration après une semaine.", "Impossible d'ouvrir la bouche normalement."],
    },
    "toux": {
        "nom": "Toux", "groupe": "Nez, gorge, toux", "mots": ["tousser", "bronchite", "toux seche", "toux grasse"],
        "principal": [], "aussi": ["antitussif", "mucolytique"],
        "gestes": ["Une toux après un rhume peut durer 2 à 3 semaines.", "Buvez bien, aérez, évitez le tabac.",
                   "Une cuillère de miel calme souvent aussi bien qu'un sirop."],
        "urgence": ["Difficulté à respirer, lèvres bleues, douleur dans la poitrine."],
        "consulter": ["Plus de 3 semaines.", "Crachats avec du sang.", "Fièvre élevée qui persiste, ou essoufflement."],
    },
    "allergie": {
        "nom": "Allergie, rhume des foins", "groupe": "Nez, gorge, toux", "mots": ["pollen", "eternuements", "acariens", "rhinite", "urticaire", "plaques"],
        "principal": ["antihistaminique", "serum_physio"], "aussi": ["corticoide_nasal", "collyre_allergie", "larmes"],
        "gestes": ["Rincez le nez et lavez vos cheveux le soir pendant la saison des pollens.", "Aérez tôt le matin ou après la pluie."],
        "urgence": ["Gonflement des lèvres, de la langue ou de la gorge.", "Difficulté à respirer, malaise."],
        "consulter": ["Sifflements en respirant ou gêne respiratoire récurrente.", "Symptômes qui persistent malgré le traitement."],
    },
    "diarrhee": {
        "nom": "Diarrhée", "groupe": "Ventre", "mots": ["gastro", "gastro-enterite", "selles liquides", "turista"],
        "principal": ["sro"], "aussi": ["loperamide"],
        "gestes": ["L'essentiel est de boire : petites quantités, souvent.", "Reprenez une alimentation légère dès que l'appétit revient.",
                   "Lavez-vous bien les mains."],
        "urgence": ["Malaise, confusion, plus d'urine depuis longtemps."],
        "consulter": ["Sang ou glaires dans les selles.", "Forte fièvre ou fortes douleurs au ventre.",
                      "Soif intense, bouche très sèche, ou impossibilité de boire.", "Plus de 2 jours sans amélioration.",
                      "Pendant ou après un traitement antibiotique, ou au retour de voyage."],
    },
    "nausees": {
        "nom": "Nausées, vomissements", "groupe": "Ventre", "mots": ["vomir", "gastro", "haut-le-coeur", "mal au coeur"],
        "principal": ["sro"], "aussi": ["domperidone"],
        "gestes": ["Attendez un peu, puis buvez de très petites gorgées, souvent.", "Reprenez à manger progressivement, sans gras."],
        "urgence": ["Vomissements avec du sang ou aspect de marc de café.", "Avec nuque raide, violent mal de tête, ou après un choc à la tête.",
                    "Douleur dans la poitrine ou forte douleur au ventre."],
        "consulter": ["Plus de 24 à 48 heures, ou impossibilité de garder la moindre boisson.", "Possibilité de grossesse.",
                      "Si vous prenez un traitement important, il peut ne pas être absorbé : demandez conseil."],
    },
    "constipation": {
        "nom": "Constipation", "groupe": "Ventre", "mots": ["transit", "selles dures", "laxatif"],
        "principal": ["fibres", "macrogol", "lactulose"], "aussi": ["glycerine", "laxatif_stimulant"],
        "gestes": ["Buvez davantage, mangez des fibres (fruits, légumes, céréales complètes), bougez chaque jour."],
        "urgence": ["Ventre gonflé et très douloureux avec vomissements, sans gaz ni selles."],
        "consulter": ["Plus de 2 semaines, ou changement récent et inhabituel après 50 ans.", "Sang dans les selles ou amaigrissement."],
    },
    "estomac": {
        "nom": "Brûlures d'estomac", "groupe": "Ventre", "mots": ["reflux", "acidite", "aigreurs", "digestion", "indigestion"],
        "principal": ["antiacide"], "aussi": ["ipp"],
        "gestes": ["Repas plus légers, pas de coucher juste après manger.", "Surélevez la tête du lit, limitez alcool, tabac et plats gras."],
        "urgence": ["Douleur dans la poitrine, le bras ou la mâchoire, avec essoufflement ou sueurs.",
                    "Vomissements de sang ou selles noires."],
        "consulter": ["Difficulté à avaler ou amaigrissement.", "Plus de 2 semaines malgré le traitement, ou premiers symptômes après 50 ans."],
    },
    "ballonnements": {
        "nom": "Ballonnements, crampes de ventre", "groupe": "Ventre", "mots": ["gaz", "spasmes", "colique", "mal au ventre"],
        "principal": ["simeticone", "antispasmodique"], "aussi": ["paracetamol"],
        "gestes": ["Mangez lentement, limitez boissons gazeuses et aliments qui fermentent.", "Une bouillotte soulage les crampes."],
        "urgence": ["Douleur violente et brutale, ventre dur, ou douleur en bas à droite avec fièvre."],
        "consulter": ["Douleurs qui reviennent souvent, sang dans les selles, amaigrissement."],
    },
    "transport": {
        "nom": "Mal des transports", "groupe": "Ventre", "mots": ["voiture", "bateau", "avion", "naupathie"],
        "principal": ["mal_transport"], "aussi": [],
        "gestes": ["Regardez au loin, aérez, placez-vous à l'avant.", "Évitez de lire et les repas lourds avant le trajet."],
    },
    "hemorroides": {
        "nom": "Hémorroïdes", "groupe": "Intime", "mots": ["anus", "demangeaisons anales", "fissure"],
        "principal": ["hemorroides"], "aussi": ["paracetamol", "macrogol", "fibres"],
        "gestes": ["Évitez la constipation et les efforts prolongés aux toilettes.", "Un bain de siège tiède soulage."],
        "consulter": ["Tout saignement qui se répète : il faut en vérifier la cause.", "Douleur forte, boule dure et bleutée.", "Plus d'une semaine sans amélioration."],
    },
    "cystite": {
        "nom": "Brûlures en urinant", "groupe": "Intime", "mots": ["cystite", "infection urinaire", "uriner", "vessie"],
        "principal": [], "aussi": ["paracetamol"],
        "gestes": ["Buvez beaucoup d'eau en attendant le médecin.", "Rien dans une pharmacie familiale ne traite une infection urinaire : un avis est nécessaire."],
        "urgence": [],
        "consulter": ["Dans tous les cas, sous 24 à 48 heures.", "Rapidement en cas de fièvre, de douleur dans le bas du dos ou de sang dans les urines.",
                      "Toujours pour un homme, en cas de grossesse, ou si cela revient souvent."],
    },
    "mycose_vaginale": {
        "nom": "Démangeaisons vaginales", "groupe": "Intime", "mots": ["mycose", "candidose", "pertes"],
        "principal": ["antifongique_gyneco"], "aussi": [],
        "gestes": ["Toilette intime douce, sans savon parfumé.", "Sous-vêtements en coton."],
        "consulter": ["S'il s'agit de la première fois.", "En cas de grossesse.", "Pertes malodorantes, fièvre ou douleur au ventre.",
                      "Si cela revient plus de 3 à 4 fois par an, ou sans amélioration après le traitement."],
    },
    "piqure": {
        "nom": "Piqûre d'insecte", "groupe": "Peau et petits accidents", "mots": ["moustique", "guepe", "abeille", "demangeaison", "taon"],
        "principal": ["froid", "antihistaminique_gel"], "aussi": ["antihistaminique", "hydrocortisone", "antiseptique"],
        "gestes": ["Retirez le dard s'il y en a un, puis nettoyez à l'eau et au savon.", "Ne grattez pas : mettez du froid."],
        "urgence": ["Gonflement du visage, des lèvres ou de la gorge, difficulté à respirer, malaise.",
                    "Piqûre dans la bouche ou la gorge."],
        "consulter": ["Rougeur qui s'étend, chaleur, fièvre ou pus.", "Gonflement très étendu."],
    },
    "tique": {
        "nom": "Morsure de tique", "groupe": "Peau et petits accidents", "mots": ["lyme", "borreliose"],
        "principal": ["tire_tique", "antiseptique"], "aussi": [],
        "gestes": ["Retirez-la le plus vite possible, sans l'écraser ni y mettre de produit.",
                   "Désinfectez, puis notez la date et l'endroit de la morsure.",
                   "Surveillez la peau pendant 4 semaines."],
        "consulter": ["Tache rouge qui s'étend autour de la morsure, même des semaines après.",
                      "Fièvre, grande fatigue ou douleurs articulaires dans les semaines qui suivent.",
                      "Tête de la tique qu'on ne parvient pas à retirer, avec rougeur."],
    },
    "plaie": {
        "nom": "Petite plaie, écorchure", "groupe": "Peau et petits accidents", "mots": ["coupure", "griffure", "egratignure", "griffe"],
        "principal": ["antiseptique", "pansement"], "aussi": [],
        "gestes": ["Lavez à l'eau et au savon, puis séchez.", "Comprimez 10 minutes si cela saigne.", "Protégez avec un pansement propre."],
        "urgence": ["Saignement abondant qui ne s'arrête pas malgré la compression."],
        "consulter": ["Plaie profonde, qui s'ouvre, ou avec un corps étranger.", "Morsure d'animal.",
                      "Rougeur qui s'étend, chaleur, pus, fièvre.", "Dernier rappel de vaccin contre le tétanos il y a plus de 10 ans."],
    },
    "brulure": {
        "nom": "Brûlure légère", "groupe": "Peau et petits accidents", "mots": ["ebouillante", "four", "cloque"],
        "principal": ["soin_brulure", "paracetamol"], "aussi": ["pansement"],
        "gestes": ["Refroidissez tout de suite sous l'eau tempérée pendant au moins 15 à 20 minutes.",
                   "Retirez bagues et montre.", "Ne percez pas les cloques, n'appliquez ni beurre ni dentifrice."],
        "urgence": ["Brûlure très étendue, chimique ou électrique.", "Sur le visage ou le cou, ou avec une gêne pour respirer."],
        "consulter": ["Plus grande que la paume de la main, ou avec de grosses cloques.", "Sur les mains, les pieds, les plis ou les organes génitaux.",
                      "Peau blanche ou noire, ou insensible."],
    },
    "coup_de_soleil": {
        "nom": "Coup de soleil", "groupe": "Peau et petits accidents", "mots": ["soleil", "insolation"],
        "principal": ["soin_brulure", "paracetamol"], "aussi": ["ibuprofene"],
        "gestes": ["Mettez-vous à l'ombre, rafraîchissez la peau et buvez.", "Ne percez pas les cloques et protégez la zone du soleil."],
        "urgence": ["Confusion, malaise, forte fièvre après une exposition à la chaleur."],
        "consulter": ["Cloques étendues, fièvre, frissons, vomissements."],
    },
    "ampoule": {
        "nom": "Ampoule au pied", "groupe": "Peau et petits accidents", "mots": ["cloque", "frottement", "chaussure"],
        "principal": ["pansement_ampoule"], "aussi": ["antiseptique", "pansement"],
        "gestes": ["Ne la percez pas si elle est intacte.", "Si elle est ouverte, nettoyez et protégez sans arracher la peau."],
        "consulter": ["Rougeur qui s'étend, pus, chaleur.", "Toute plaie au pied en cas de diabète."],
    },
    "mycose_peau": {
        "nom": "Mycose de la peau ou des pieds", "groupe": "Peau et petits accidents", "mots": ["pied d'athlete", "champignon", "orteils", "intertrigo"],
        "principal": ["antifongique"], "aussi": [],
        "gestes": ["Gardez la zone propre et bien sèche.", "Changez de chaussettes chaque jour, alternez les chaussures."],
        "consulter": ["Atteinte des ongles ou du cuir chevelu.", "Pas d'amélioration après 2 à 4 semaines.", "Diabète ou baisse d'immunité."],
    },
    "demangeaisons": {
        "nom": "Démangeaisons, plaques", "groupe": "Peau et petits accidents", "mots": ["urticaire", "eczema", "rougeur", "gratter", "boutons"],
        "principal": ["antihistaminique"], "aussi": ["hydrocortisone", "antihistaminique_gel"],
        "gestes": ["Évitez la chaleur, les savons parfumés et de gratter.", "Pensez à ce qui est nouveau : médicament, aliment, lessive."],
        "urgence": ["Gonflement des lèvres, de la langue ou de la gorge, difficulté à respirer, malaise."],
        "consulter": ["Après la prise d'un nouveau médicament : arrêtez et demandez conseil.", "Fièvre, atteinte des muqueuses, peau qui se décolle.",
                      "Plus d'une semaine sans amélioration."],
    },
    "herpes": {
        "nom": "Bouton de fièvre", "groupe": "Yeux, bouche, oreilles", "mots": ["herpes", "levre"],
        "principal": ["antiherpes"], "aussi": ["paracetamol"],
        "gestes": ["Commencez dès les premiers picotements.", "Ne touchez pas le bouton et évitez de le transmettre : pas de bisou ni de partage de verre."],
        "consulter": ["Plus de 10 jours, ou très étendu.", "Atteinte de l'œil.", "Baisse d'immunité."],
    },
    "aphte": {
        "nom": "Aphtes", "groupe": "Yeux, bouche, oreilles", "mots": ["bouche", "ulcere bouche"],
        "principal": ["gel_buccal"], "aussi": ["paracetamol"],
        "gestes": ["Évitez les aliments acides, épicés ou très salés.", "Brossage doux."],
        "consulter": ["Plus de 2 semaines.", "Très nombreux, très douloureux, ou qui reviennent souvent.", "Avec de la fièvre."],
    },
    "dents": {
        "nom": "Mal de dents", "groupe": "Yeux, bouche, oreilles", "mots": ["dentaire", "gencive", "molaire", "abces"],
        "principal": ["paracetamol", "ibuprofene"], "aussi": ["naproxene"],
        "gestes": ["Prenez rendez-vous chez le dentiste : l'antidouleur ne soigne pas la cause.", "Évitez le très chaud, le très froid et le sucré."],
        "urgence": ["Gonflement du visage ou du cou avec difficulté à respirer ou à avaler."],
        "consulter": ["Joue gonflée ou fièvre : dentiste ou médecin rapidement.", "Douleur qui dure plus de 2 jours."],
    },
    "yeux": {
        "nom": "Yeux secs ou irrités", "groupe": "Yeux, bouche, oreilles", "mots": ["oeil", "conjonctivite", "yeux rouges", "lentilles", "orgelet"],
        "principal": ["larmes", "serum_physio"], "aussi": ["collyre_allergie"],
        "gestes": ["Faites des pauses d'écran, clignez des yeux.", "Retirez vos lentilles tant que l'œil est irrité.",
                   "Ne partagez ni serviette ni collyre."],
        "urgence": ["Baisse brutale de la vue, ou douleur vive à l'œil.", "Produit chimique dans l'œil : rincez 15 minutes à l'eau claire, puis appelez."],
        "consulter": ["Œil rouge et douloureux, surtout avec des lentilles.", "Pas d'amélioration après 2 à 3 jours, ou pus abondant.", "Corps étranger qui reste."],
    },
    "oreille": {
        "nom": "Mal d'oreille", "groupe": "Yeux, bouche, oreilles", "mots": ["otite", "bouchon"],
        "principal": ["paracetamol"], "aussi": ["ibuprofene"],
        "gestes": ["N'introduisez ni coton-tige ni gouttes dans une oreille douloureuse."],
        "consulter": ["Écoulement, fièvre, baisse de l'audition.", "Gonflement derrière l'oreille.", "Douleur qui dure plus de 2 jours."],
    },
    "insomnie": {
        "nom": "Difficulté à dormir", "groupe": "Sommeil", "mots": ["insomnie", "sommeil", "nuit", "decalage horaire", "stress"],
        "principal": [], "aussi": ["melatonine", "valeriane"],
        "gestes": ["Couchez-vous et levez-vous à heures régulières.", "Pas d'écran ni de café en soirée, chambre fraîche et sombre.",
                   "Si vous ne dormez pas après 20 minutes, levez-vous un moment."],
        "consulter": ["Plus de 3 semaines, ou retentissement sur la journée.", "Idées noires : parlez-en sans attendre (0800 32 123, écoute 24h/24)."],
    },
}

URGENCE_GENERALE = [
    {"nom": "Urgence vitale", "numero": "112", "detail": "Douleur dans la poitrine, gêne pour respirer, malaise, signes d'AVC"},
    {"nom": "Centre Antipoisons", "numero": "070 245 245", "detail": "Erreur de dose ou produit avalé, 24h/24"},
    {"nom": "Médecin de garde", "numero": "1733", "detail": "Nuit, week-end et jours fériés, si cela ne peut pas attendre"},
]
PHARMACIE_DE_GARDE = "https://www.pharmacie.be"

# Trousse de base, d'après la liste de contrôle de Multipharma (voir SOURCES.md), sans ce qui n'est pas un soin.
ESSENTIELS = [
    "paracetamol", "ibuprofene", "thermometre", "pansement", "pansement_ampoule", "antiseptique", "tire_tique",
    "soin_brulure", "ains_gel", "hydrocortisone", "froid", "serum_physio", "decongestionnant", "pastille_gorge",
    "antihistaminique", "antiacide", "loperamide", "sro", "macrogol", "mal_transport", "larmes",
]


def normaliser(texte):
    """Minuscules, sans accent ni ponctuation superflue, pour comparer des noms."""
    sans = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+\-' ]", " ", sans.lower())).strip()


_ALIAS = sorted(((normaliser(a), cle) for cle, s in SUBSTANCES.items() for a in s["alias"]), key=lambda x: -len(x[0]))


def trouver_substances(texte):
    """Clés du catalogue reconnues dans un texte (nom de marque ou substance). L'ordre suit le catalogue."""
    propre = " " + normaliser(texte) + " "
    trouve = set()
    for alias, cle in _ALIAS:  # du plus long au plus court : « ibuprofène gel » n'est pas de l'ibuprofène en comprimé
        motif = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        if re.search(motif, propre):
            trouve.add(cle)
            propre = re.sub(motif, " ", propre)
    return [c for c in SUBSTANCES if c in trouve]


def maux_de_substance(cle):
    return [m for m, d in MAUX.items() if cle in d["principal"] or cle in d["aussi"]]


def verifier():
    """Cohérence du catalogue : renvoie la liste des erreurs."""
    erreurs = []
    for cle, m in MAUX.items():
        if m["groupe"] not in GROUPES:
            erreurs.append(f"{cle} : groupe inconnu")
        for s in m["principal"] + m["aussi"]:
            if s not in SUBSTANCES:
                erreurs.append(f"{cle} : substance inconnue {s}")
        if not m.get("gestes"):
            erreurs.append(f"{cle} : aucun geste")
    for cle, s in SUBSTANCES.items():
        if s.get("deconseille") and maux_de_substance(cle):
            erreurs.append(f"{cle} : déconseillé mais proposé")
        if cle == "antibiotique" and maux_de_substance(cle):
            erreurs.append("antibiotique proposé pour un mal")
    return erreurs
