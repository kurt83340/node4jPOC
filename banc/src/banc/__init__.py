"""Banc d'essai de la technique 2 (agent text-to-Cypher) : spec 002-agent-text-to-cypher."""

import warnings

# ADK 2.11.0 avertit sur stderr, une fois par processus, qu'une fonction expérimentale est active
# (« [EXPERIMENTAL] feature FeatureName.PLUGGABLE_AUTH is enabled. ») : il le fait dès son import,
# en créant une classe expérimentale (google/adk/features/_feature_registry.py). Bruit relevé en
# T5.1, sans rapport avec la mesure. Le filtre se pose ici, à l'import du paquet, avant celui
# d'ADK : python -m banc.cellule_adk charge banc avant la cellule.
warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\] feature ", category=UserWarning)
