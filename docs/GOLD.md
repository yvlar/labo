# Spécialisation XAU/USD — version 0.2.0

Le laboratoire traite exclusivement l’or contre USD. Cette version ajoute un modèle de contrat explicite, un contexte de volatilité causal, des horaires fournisseur, des sessions et des protections d’entrée propres au profil Gold. Ces fonctionnalités ne démontrent aucune efficacité de trading. Les paramètres ci-dessous sont des hypothèses du projet, enregistrées H11–H15, sans attribution à OlinVest.

## Contrat et unités

`symbol=XAUUSD`, `base_currency=XAU`, `currency=USD`, `price_unit=USD_per_troy_ounce`, `quantity_unit=contract`. `contract_size` désigne les onces troy par contrat. Une variation de prix de1USD/once vaut donc `contract_size` USD par contrat : `point_value` doit lui être égal. Valeur du tick par contrat=`tick_size*contract_size` ; exposition en onces=`qty*contract_size`.

`product_type` est explicitement `spot_otc` ou `cfd`. Futur, ETF ou indice refusés, même si leur symbole est renommé XAUUSD. `fixture` est réservé aux données déclarées synthétiques des tests. Aucune taille universelle de lot Gold, aucun tick universel ni frais de courtier n’est supposé. L’exemple fourni décrit hypothétiquement un contrat de1once ; il porte `verified=false` et n’est pas utilisable pour une recherche ou un flux actuel de marché.

Le minimum de quantité, l’incrément, la marge, les commissions et le financement doivent utiliser cette même unité contractuelle. La simulation reste interne. Le financement reste une approximation quotidienne UTC, commune aux deux directions ; un financement réel variable par direction/rollover fournisseur n’est pas encore reproduit.

## Cotation fournisseur et fermetures

`market_sessions` décrit les horaires hebdomadaires du fournisseur, sous forme de liste. Chaque objet contient `weekdays` (lundi0 à dimanche6), `start`, `end` (HH:MM) et `timezone` (IANA). Une fin antérieure ou égale au début correspond au lendemain ; début=fin signifie24heures. Les sessions qui chevauchent minuit et les changements DST sont calculés dans le fuseau déclaré. Aucun calendrier réel n’est prérempli. `market_sessions_source` doit documenter leur provenance avant `verified=true`.

`market_closures` est une liste d’exceptions connues : `start`, `end`, `available_at` en ISO avec fuseau, `reason` et `source`. Les interruptions planifiées doivent être connues avant leur début. Une fermeture future non encore connue n’agit pas sur les décisions passées. Les nouvelles entrées sont bloquées hors cotation et pendant les5minutes précédant une fermeture connue. Le calcul de la pause repose exclusivement sur ce calendrier fourni ; il ne découvre pas automatiquement les jours fériés, fermetures anticipées ou changements historiques d’horaires. Le calendrier doit correspondre à la période des données.

Le fichier d’exemple laisse horaires et source vides. La commande suivante explicite les blocages sans simuler de cotation :

```bash
python -m lab.cli gold-status
python -m lab.cli gold-status --metadata /chemin/instrument-verifie.json
```

## Volatilité et distances

TR M1=`max(high-low, abs(high-close_previous), abs(low-close_previous))` au bid. Pour la première bougie d’une séquence, TR=high-low. ATR=SMA des14derniers TR, disponible après clôture, en USD/once troy. Un trou remet à zéro cette fenêtre ; aucune interpolation ni ATR d’une bougie future. Importer une antériorité suffisante avant la première ouverture à analyser. Sans14M1 contiguës, les protections actives refusent une nouvelle entrée.

La classification faible/normale/élevée compare l’ATR courant à la médiane des60ATR **antérieurs**. Faible si ratio<0,75 ; élevée si>1,5 ; sinon normale. Tant que l’antériorité manque, régime indéterminé. Cette classification sert à décrire les résultats ; elle ne choisit ni modèle, ni unité de temps, ni risque, ni stop après observation du résultat.

Les marges structurelles sont désormais exprimées en ticks du contrat : cassure1tick, égalité5ticks. Les valeurs effectives en USD/once sont conservées dans chaque snapshot et rapport. Les anciens champs absolus de primitives restent documentés comme référence historique ; le profil Gold détermine les valeurs effectives v0.2.0.

## Protections avant entrée

| Vérification | Convention initiale |
|---|---|
| Antériorité ATR |14M1 contiguës |
| Spread / ATR |≤0,30 |
| Spread / distance du stop |≤0,20 |
| Distance minimale du stop |≥2ticks |
| Avant fermeture fournisseur connue |Refus à≤5minutes |
| Calendrier USD |Optionnel, désactivé tant que non renseigné |

Ces seuils sont fixés avant toute mesure de marché et ne sont pas des seuils optimisés. Une comparaison sans protections est disponible avec `configs/gold-observation.json` ; le contexte Gold y reste calculé. Les modèles et les sorties de base ne sont pas fusionnés avec un score arbitraire.

À la décision : utiliser le spread de clôture et l’ATR connu à cette clôture. Au remplissage : réexaminer le spread **d’ouverture de la prochaine M1**, le stop prévu et l’ATR de la clôture précédente. Les high/low futurs de la bougie de remplissage ne peuvent pas rendre son spread acceptable. Les ordres limites conservent l’approximation de spread observé à l’ouverture ; le spread intrabougie et la queue restent inconnus.

Un rejet de protection génère `GOLD_SIGNAL_REFUSED` ou `ORDER_REFUSED`, avec mesures et motif. Une dégradation de ces conditions ne supprime jamais une position : stops et sorties existants continuent d’être simulés avec les prochains prix, y compris en gap.

## Sessions de contexte

| Étiquette | Fenêtre locale | Fuseau |
|---|---|---|
| ASIE |09:00–17:00 |Asia/Tokyo |
| LONDRES |08:00–16:30 |Europe/London |
| NEW_YORK |08:00–17:00 |America/New_York |

Fenêtres de programmation du projet, en semaine, indépendantes du calendrier réel du fournisseur. Elles n’authentifient pas les heures locales incertaines de S6. L’OPR reste09:30America/New_York et n’est pas redéfini par cette table. Le chevauchement Londres/New York tient compte des semaines de changement d’heure différentes.

Les extrêmes d’une session sont publiés dans `GOLD_SESSION_COMPLETE` uniquement après son terme et si toutes les M1 attendues sont présentes et contiguës. Sinon `GOLD_SESSION_INCOMPLETE` : aucun extrême final inventé. Le contexte conserve les dernières sessions complètes ; ces niveaux sont informatifs et ne deviennent pas automatiquement des sweeps ou filtres d’entrée. Les régimes statistiques utilisent la priorité exclusive New York→Londres→Asie pour éviter de compter deux fois un même trade, tout en conservant toutes les sessions actives dans les raisons.

## Annonces USD optionnelles

Le champ `gold.usd_calendar.events` accepte des événements planifiés avec `id`, `title`, `currency=USD`, `scheduled_at`, `available_at`, `source`. Le filtre optionnel bloque15minutes avant et après l’horaire prévu, uniquement si le programme était déjà connu à cet instant. Aucun résultat macroéconomique, surprise, chiffre final ou titre futur n’intervient. Aucun fournisseur d’actualités n’est connecté. Activer le filtre avec un calendrier vide est refusé. Le jeu d’événements doit couvrir la période étudiée ; une liste non vide ne prouve pas à elle seule son exhaustivité.

Ces annonces n’appartiennent pas à la méthode S1 sans actualités : c’est un ajout distinct du projet à comparer, jamais une règle implicitement attribuée à cette source.

## Reproductibilité et limites

Profils et événements planifiés sont inclus dans la configuration figée, les hashes et le journal. Chaque trade conserve le contexte Gold de sa décision et le contrôle de remplissage. Le rapport ajoute les résultats par session Gold et régime causal, ainsi que le spread/ATR à décision. Aucune statistique de ce type n’a encore été mesurée sur le marché.

La version0.2.0 change les contrôles d’entrée. Une ancienne expérience prospective ne doit pas reprendre avec ce code : nouveau nom d’expérience, sans effacement de l’historique. Les tests synthétiques contrôlent le logiciel ; données de marché, contrats et calendriers vérifiés restent nécessaires. Aucune connexion courtier ni surveillance permanente active.
