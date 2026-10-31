import logging
import os

from .server import demarrer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
demarrer(os.environ.get("PHARMACIE_BASE", "/data/pharmacie.db"), port=int(os.environ.get("PHARMACIE_PORT", "8099")))
