# O / LAB — laboratoire quantitatif OlinVest

Laboratoire exclusivement consacré à **XAU/USD (or contre dollar américain)**. Le symbole des métadonnées doit être exactement `XAUUSD` ; les autres instruments sont refusés à l’import, dans le moteur, en recherche et en simulation directe.

Interprétation programmable de contenus publics, sans certification ni accès à une méthode privée. Le succès recherché est une mesure reproductible, y compris négative. **Aucune connexion de courtage, aucun ordre réel, aucun bouton de passage en réel.**

## Démarrage local

Python 3.11+ ; aucune dépendance à installer pour CSV, moteur, tests et interface.

```bash
cd /workspace/olinv-lab
python -m unittest discover -v
python -m lab.cli check-config --config configs/primary.json
python -m lab.cli serve --port 8080
```

Ouvrir http://127.0.0.1:8080. Arrêter avec **Ctrl-C**. Le serveur est local et en lecture seule. Aucun hébergement n’a été créé. Les tableaux restent vides tant qu’aucune donnée de marché vérifiée n’est importée.

## Import de données de marché

Fournir des bougies **M1**, horodatées à l’ouverture, UTC explicite, bid/ask séparés :

```text
time,open,high,low,close,ask_open,ask_high,ask_low,ask_close,volume
```

Les colonnes non préfixées sont le bid. `volume` peut être vide si absent. Le schéma sans données est dans `data/schema.csv`. Les bougies doivent être clôturées, strictement croissantes, sans doublon. Aucune réparation ni interpolation automatique. Les gaps sont conservés et signalés ; les unités supérieures incomplètes sont rejetées.

Copier `configs/instrument.example.json` vers un fichier local et **renseigner les spécifications réelles du fournisseur**, leur provenance et les droits d’usage avant `verified: true`. Les valeurs du modèle sont illustratives et ne sont pas celles d’un courtier. `point_value` est le résultat en USD d’une variation de prix de 1 pour une unité de quantité ; `contract_size` décrit cette unité contractuelle. La quantité et ses incréments doivent utiliser cette même convention. Financement positif = coût facturé par unité et jour UTC ; c’est une approximation explicite. Les devises autres qu’USD sont bloquées, sans conversion inventée. Un XAUUSD CFD n’est pas un futur GC ; aucune substitution.

```bash
python -m lab.cli import-data --file /chemin/xauusd.csv --metadata /chemin/instrument.json
```

La commande affiche `data/normalized/<sha256>`. Les octets bruts sont conservés dans `data/raw/<sha256>`. Le manifeste inclut les empreintes, la qualité, la période et les métadonnées. Les données et journaux locaux sont exclus de Git. Parquet est pris en charge si `pandas` et `pyarrow` sont disponibles ; utiliser CSV sinon.

## Rejeu causal

```bash
python -m lab.cli history --config configs/primary.json --dataset data/normalized/EMPREINTE --experiment xau-rejeu-001
python -m lab.cli serve
```

Sélectionner l’expérience dans l’interface. Le curseur et les boutons avancent le préfixe traité. Les données et objets après l’instant choisi ne sont pas renvoyés au navigateur. Le rejeu montre les décisions du portefeuille avec priorité lexicographique ; les comparaisons de recherche isolent chaque modèle.

## Recherche et hors échantillon

Fixer **avant consultation des résultats** le découpage de `configs/splits.example.json`, les paramètres, coûts et modèles. `primary.json` contient M1 H1/M5 et H4/M15, M5A et M5B. `variants.json` contient les ablations isolées, M2/M3, M4/M6 et une baseline de cassure OPR simple, avec budget maximum 120 expériences.

```bash
python -m lab.cli preregister --config configs/variants.json --dataset data/normalized/EMPREINTE --splits /chemin/splits.json --experiment xau-recherche-001
python -m lab.cli evaluate --experiment xau-recherche-001
```

Le préenregistrement fige configuration complète, code, commit, données, périodes, budget, métrique et critères d’échec. Aucune optimisation automatique. Chaque modèle est évalué avec coûts/spread/slippage ×1, ×2 et ×3. L’apprentissage, la validation et le test sont chronologiques ; les paramètres restent identiques pendant les fenêtres prospectives successives (walk-forward à paramètres fixes, sans réentraînement). Les transactions chevauchant une frontière sont exclues des statistiques de trades et comptées ; l’état du compte et son risque restent continus.

`report.json`, `report.md`, événements et transactions sont écrits dans `runs/<expérience>/`. Le témoin `test-access.json` est créé **avant** évaluation : même un échec technique ne restaure pas un test intact. La reproduction se fait dans une copie conservant la mention de consultation. Après modification, prévoir une nouvelle réserve temporelle ; renommer une expérience ne rend pas les mêmes données indépendantes.

Le bootstrap regroupe les transactions par journée UTC (1 000 réplications, graine 17). Moins de 100 transactions ou intervalle contenant zéro : non concluant. Borne haute ≤0 : échec selon le protocole. Aucun chiffre annualisé. La concentration quotidienne et l’attrition aux frontières doivent être examinées avec les statistiques. Les exemples vidéo restent pédagogiques, jamais un échantillon de validation.

## Simulation directe bornée

Un exporteur de données **déjà autorisé** doit écrire un fichier JSONL append-only : une ligne = mêmes champs qu’une bougie CSV M1 clôturée. Le laboratoire n’ouvre aucun compte, n’intègre aucun SDK courtier et n’active aucun endpoint externe. Aucun exporteur fournisseur n’est configuré ici.

```bash
python -m lab.cli live --config configs/primary.json --metadata /chemin/instrument.json --feed /chemin/m1-courant.jsonl --experiment xau-prospectif-001 --seconds 10 --max-age 90
```

Pour une exécution prolongée sous votre supervision, par exemple huit heures :

```bash
python -m lab.cli live --config configs/primary.json --metadata /chemin/instrument.json --feed /chemin/m1-courant.jsonl --experiment xau-prospectif-001 --seconds 28800 --max-age 90
```

Arrêt : **Ctrl-C** ; entrées, décisions et positions sont conservées en SQLite. Relancer exactement la même commande/expérience reprend par rejeu déterministe et idempotent ; un changement de code, métadonnées ou paramètres exige une nouvelle expérience. Le fichier peut être relu depuis son début sans dupliquer les événements. Un processus durable (service système, superviseur local) est à configurer pour la permanence ; aucun n’est lancé par ce projet.

Un contrôle de connexion sans instrument ni exécution peut être lancé avec `python -m lab.cli probe --feed /chemin/m1-courant.jsonl --seconds 3`. Il vérifie seulement la présence du fichier, sans valider son contenu ni créer de transaction. Le contrôle livré a terminé en attente de flux, puis s’est arrêté.

La fraîcheur est contrôlée à chaque réception et à chaque boucle. Un flux absent/périmé bloque les entrées. Une correction ou donnée tardive non identique verrouille l’expérience jusqu’à examen ; le journal n’est pas réécrit. Un trou annule les ordres en attente et les confirmations, conserve les positions et traite leurs protections au prochain prix reçu, avec gaps défavorables. Sans cotation nouvelle, aucune clôture ou valorisation actuelle n’est inventée. SQLite est l’autorité ; `snapshot.json` est une projection d’affichage.

## Documents

- `docs/RULES.md`, `docs/rules.json` : registre des règles, passages, hypothèses et divergences.
- `docs/sources/` : transcriptions automatiques et textes publics effectivement récupérés.
- `docs/SPECIFICATION.md` : ordre de traitement, formules et états.
- `docs/EXPERIMENTS.md` : protocole et registre initial.
- `reports/STATUS.md` : vérification logicielle, blocages, absence de mesures de marché et limites.

Les données synthétiques sont confinées aux tests. Les commandes de rapport, rejeu utilisateur et simulation directe refusent les données déclarées synthétiques. Aucune promesse commerciale de gain ou taux de réussite ne guide le protocole.
