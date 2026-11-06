# Commandes de reproduction

Toutes les commandes se lancent depuis `/workspace/olinv-lab`. Source corrective et empreintes : `verdicts.json`. Référence avant modification : commit `24e2258`, fichiers `baseline/`. Les commandes suivantes ne passent aucun ordre réel.

## Vérifications déjà exécutables sans clé

```bash
cd /workspace/olinv-lab
python -m unittest discover -v
node --check web/app.js
python -m lab.cli gold-status
python -m tests.audit_workflow --output reports/audit/reproduction-nouvelle-copie
```

La dernière commande produit sept jeux **synthétiques de tests logiciels**, les importe par la CLI normale, vérifie les préfixes et la parité par `StreamingSession`, puis exporte deux graphiques par cas. Elle ne calcule ni ne publie de performance de marché. Son dossier de destination doit être nouveau. Matplotlib est nécessaire pour les PNG (installé dans l’environnement de cet audit ; option Python `audit` du projet si nécessaire).

`final-checked/commands.json` conserve les21commandes import/verify/export exactes exécutées pendant l’audit, avec les chemins des CSV, configurations et empreintes réelles de ces fixtures. Ces chemins ne désignent pas des cotations Gold de marché. `tests-final.txt` conserve les tests réellement passés.

## 1. Import XAU/USD réel

Précondition manquante : déposer `inputs/oanda-xauusd-m1.csv` et `inputs/oanda-xauusd.metadata.json`, ou un export d’un autre fournisseur explicitement identifié. Aucune API de téléchargement n’est intégrée ni clé configurée. L’export doit contenir des M1 UTC clôturées avec bid et ask séparés, sans substitution d’actif.

À partir de `configs/instrument.example.json`, documenter les caractéristiques effectives puis vérifier le fichier : `provider`, `provider_symbol` réellement exporté, `product_type`, `account_currency`, onces par contrat, tick, incréments, marge, commissions/financement, prix/volume, calendrier et provenance. `verified=true` est une attestation de ces informations, pas une authentification automatique du CSV. Pour OANDA : symbole API conventionnel `XAU_USD`, référence graphique `OANDA:XAUUSD`; la disponibilité effective dépend du compte/service. Compte CAD actuellement refusé.

```bash
XAU_DATASET_DIR=$(python -m lab.cli import-data --file inputs/oanda-xauusd-m1.csv --metadata inputs/oanda-xauusd.metadata.json)
```

La commande affiche le dossier normalisé et crée son manifeste avec empreintes. Sans ces deux fichiers, cette étape reste bloquée. Le type de produit, les horaires et frais du fichier d’exemple ne sont pas des spécifications OANDA vérifiées. Si un autre fournisseur est utilisé, son nom reste dans les rapports ; aucune comparaison de prix OANDA/autre n’a été faite ici faute de séries communes.

## 2. Backtest d’une méthode

Déposer `inputs/splits-fixes.json` avec `start`, `train_end`, `validation_end`, `end` en ISO UTC, dans la période disponible, et réserver un test final non consulté. Ne pas utiliser les dates d’exemple comme une réserve réelle ni modifier les paramètres après consultation du test.

```bash
python -m lab.cli preregister --config reports/audit/configs/M1-H1-M5.json --dataset "$XAU_DATASET_DIR" --splits inputs/splits-fixes.json --experiment xau-m1-reference-001
python -m lab.cli evaluate --experiment xau-m1-reference-001
```

Pour M5, utiliser `reports/audit/configs/M5A-80-range.json` ou `M5B-80-range.json` et un autre nom d’expérience préenregistré. Chaque méthode est isolée. Le calcul publie coûts×1/×2/×3, données/configuration/commit/périodes, non-fill et métriques ; il refuse toute donnée synthétique ou non vérifiée. La consultation du test final est marquée avant calcul. Après changement des règles, utiliser une nouvelle réserve ou une validation prospective, pas seulement un nom différent.

Les comparaisons demandées sont regroupées dans `configs/audit-comparisons.json` :18modèles,54simulations sous budget120. M1/direct et M2/parent partagent les identifiants de zones HTF ; M5 partage la même OPR journalière. Les paires partiel/sortieunique ont un filtre de cible commun>2R. Les protections Gold restent les mêmes pour ces paires ; `gold-observation.json` est une autre expérience à figer séparément, pas un choix après résultat.

## 3. Rejeu graphique et deux vues d’une décision

```bash
python -m lab.cli history --config reports/audit/configs/M1-H1-M5.json --dataset "$XAU_DATASET_DIR" --experiment xau-rejeu-001
python -m lab.cli serve --port 8080
```

Ouvrir http://127.0.0.1:8080 et avancer le curseur. Aucun objet futur n’est envoyé par le serveur de rejeu. Arrêt Ctrl-C. Ce serveur n’a pas pu écouter dans le sandbox de l’audit (`serve-attempt.txt`, PermissionError avant écoute) ; cette commande reste à exécuter dans un environnement autorisant le port local. Le Chromium automatisé n’a pas démarré ici ; pas de certification navigateur de cette version.

Pour les PNG, relever `seq` d’un événement `ENTRY_PENDING` dans le fichier d’événements produit par evaluate, puis fixer la variable `XAU_DECISION_SEQ` à cet entier :

```bash
python -m lab.cli export-decision --config reports/audit/configs/M1-H1-M5.json --dataset "$XAU_DATASET_DIR" --seq "$XAU_DECISION_SEQ" --output runs/xau-decision-001
```

Les vues `decision.png` et `after.png` indiquent fuseau Toronto, unités, fournisseur, zone, disponibilité, déclencheur, stop et cible. Pour une absence d’ordre, choisir le `seq` du contact/rejet : aucun stop/cible fictif n’est créé. Les PNG déjà produits dans `final-checked/` sont de gros caractères « SYNTHÉTIQUE — TEST LOGICIEL, PAS PERFORMANCE ».

## 4. Comparaison historique/rejeu en flux

```bash
python -m lab.cli verify-engine --config reports/audit/configs/M1-H1-M5.json --dataset "$XAU_DATASET_DIR" --output runs/xau-parite-001
```

Cette commande compare événements, ordres, sorties, snapshots et objets connus par préfixe, puis redémarre et injecte des doublons. Le chemin de réception est **la même classe StreamingSession que live**, avec horloge virtuelle explicitement indiquée. Cela valide la parité du modèle à bougies ; cela ne mesure pas un délai réseau, ne branche pas un service actuel et ne prouve pas qu’un open nominal sera accessible en temps réel.

La fraîcheur est calculée avec l’instant de réception ; le moteur reste un modèle de disponibilité nominale à clôture et de latence configurée (défaut0). Une validation prospective crédible devra mesurer la livraison des données et disposer d’une cotation après décision ; les ticks/arrivées effectifs ne sont pas reconstruits par ce rejeu OHLC. Cette limite doit rester dans le rapport, surtout pour le prix d’entrée M5B. Pour les fixtures exclusivement logicielles, `--software-test` est obligatoire et aucune performance n’est produite.

## 5. Session courte sur données actuelles

Précondition manquante : un exporteur autorisé doit écrire `inputs/xauusd-current.jsonl`, une M1 bid/ask clôturée par ligne, et ses métadonnées vérifiées. Aucune clé de courtage pour exécuter n’est requise ni acceptée par le moteur interne.

```bash
python -m lab.cli live --config reports/audit/configs/M1-H1-M5.json --metadata inputs/oanda-xauusd.metadata.json --feed inputs/xauusd-current.jsonl --experiment xau-prospectif-001 --seconds 10 --max-age 90
```

La commande actuelle d’audit avec les métadonnées d’exemple a correctement refusé de lancer une fausse session (`live-current-attempt.txt`). Le probe de2secondes a reçu zéro flux puis s’est arrêté. **Ce n’est pas une simulation de marché réussie.** Le verrou d’incident est désormais conservé au redémarrage ; les entrées restent arrêtées mais les protections d’une position ouverte continuent au prochain prix reçu. Les doublons identiques sont ignorés, une correction est refusée, un trou annule les ordres en attente. Reprendre exige même version/configuration ; une correction de stratégie crée une nouvelle expérience sans effacer l’ancienne.
