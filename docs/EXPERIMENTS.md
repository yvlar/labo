# Registre et protocole des expériences

Date de démarrage : 2026-11-05. Version0.1.0, branche `research/causal-lab` dans le dépôt dédié `/workspace/olinv-lab`. Aucun dépôt préexistant ni modification utilisateur n’a été remplacé ; le `.git` de la racine était un montage en lecture seule sans dépôt exploitable.

| Identifiant | Nature | Données | État |
|---|---|---|---|
| software-causal-v1 | Tests de logiciel | Fixtures synthétiques, exclusivement dans tests | Voir reports/STATUS.md |
| xau-reference | Référence et hors échantillon | XAUUSD M1 bid/ask fournisseur vérifié | BLOQUÉ, données absentes |
| prospective-connection-check | Essai borné de l’adaptateur | Aucun flux reçu | Contrôle WAITING/STOPPED, pas de signal de marché |

Les futurs enregistrements sont créés sous `runs/<id>/preregistration.json`. Fichier créé une seule fois avec hash. La commande evaluate vérifie code et empreinte des données, refuse toute donnée synthétique/non vérifiée, puis marque le test final consulté avant calcul.

Les paramètres candidats sont les modèles explicites de configs/primary.json ou variants.json. Le second contient 27 modèles avant éventuelles modifications documentées. Budget total120, coût d’exécution3 simulations par modèle (référence, stress×2, stress×3). Les fenêtres chronologiques fournies sont fixes ; aucun choix de paramètres sur test final. Les variantes sweep/FVG/contexte et politiques de sortie sont des comparaisons enregistrées, pas une recherche combinatoire. Les heures incertaines de S6, profils de volume et systèmes de scoring ne font pas partie des candidats actifs.

Métrique principale : espérance nette en R des transactions entièrement closes dans la fenêtre ; attrition de frontière publiée. Comptes continus pour conserver limites de risque et positions, purge des statistiques des trades qui chevauchent les fenêtres. Walk-forward à paramètres fixes = observation successive validation puis test sans réajustement. Il ne s’agit pas d’un optimiseur avec réentraînement. Baselines : cash0% sans rémunération et cassure OPR sans retest.

Incertitude : bootstrap par journées UTC, incluant jours observés sans transaction ;1000tirages graine17. Minimum10jours pour calculer l’intervalle ; moins100transactions reste non concluant. Borne haute de CI≤0 : échec ; intervalle contenant0 : non concluant ; borne basse>0 sur≥100trades : à confirmer prospectivement, jamais promesse. Ce critère ne corrige pas tous les biais de sélection entre variantes ; le test final ne doit pas servir à élire un gagnant puis être présenté comme intact.

Sensibilité actuelle : changements isolés de règles/stop,80vs90min et stress des coûts. Une exploration générale de paramètres de pivots ou seuils n’est pas implémentée. Toute extension consomme un nouveau budget préenregistré et requiert de nouvelles périodes de réserve. Aucun résultat ne doit être effacé parce qu’il est mauvais.

## Profil Gold0.2.0

Nouvelle version de recherche : protections Gold globales préenregistrées dans primary/variants, comparaison indépendante dans gold-observation.json. Paramètres et calendrier USD figés avec le reste de la configuration. Aucune performance mesurée, aucun nouveau gagnant sélectionné. Toute comparaison des deux profils consomme le budget de son expérience ; ne pas utiliser le test final pour fixer leurs seuils.
