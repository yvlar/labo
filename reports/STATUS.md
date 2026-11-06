# État de livraison et limites

## Ce qui est implémenté

Moteur Python déterministe commun, M1 H1/M5 et H4/M15, M5A retest/confirmation et M5B FVG, interprétations distinctes M2/M3 puis M4/M6. Primitives : pivots confirmés, HH/HL/LH/LL, cassures et CHoCH, zones pivot/base/fractale, sweeps de pivots, égalités, FVG et remplissage, Fibonacci figé, Volume Profile approximatif sur plage terminée. Registre14sources/39règles avec extraits et hypothèses.

Import CSV/Parquet, empreintes brutes/normalisées, qualité stricte sans interpolation. Simulateur bid/ask : frais, financement simplifié, latence, slippage, gaps, arrondis/marge, expirations/refus, stop prioritaire et ambiguïtés. Politiques E1–E5, partiels et R net. Journal SQLite atomique, reprise par rejeu idempotent, verrouillage en cas de correction, santé et absence de permanence implicite. Interface française locale et rejeu par préfixe serveur. Recherche préenregistrée, isolation des modèles, fenêtres chronologiques, purge statistique, bootstrap journalier et stress des coûts.

## Ce qui a été testé

Consulter `verification.json` pour le résultat final et l’empreinte du code. Les fixtures synthétiques valident le logiciel uniquement. Les parcours M1, M5A et M5B produisent décisions, fills ultérieurs et clôtures dans des scénarios contrôlés. Tests de disponibilité des pivots/zones/FVG/OPR, DST New York été/hiver, HTF incomplètes, profils futurs interdits, invariance par préfixe/futur modifié, parité/reprise SQLite, coûts/partiels/gaps/marge, données invalides et refus technique des comptes/endpoints externes.

Les autres variantes sont exécutables et testées sans exception sur fixtures ; cela ne constitue pas une validation exhaustive de chaque séquence d’entrée ni de leur fidélité aux vidéos. Les transcriptions sont automatiques ; les images et détails sensibles des vidéos n’ont pas été contrôlés visuellement.

## Mesures sur données de marché : AUCUNE

Essai d’accès public effectué à `https://datafeed.dukascopy.com/datafeed/XAUUSD/2025/00/06/BID_candles_min_1.bi5` : réponse **HTTP429 Too Many Requests**. Aucun fichier de prix exploitable, aucun fournisseur authentifié, aucune spécification contractuelle vérifiée dans l’environnement. Aucun proxy alternatif, compte ou accès privé utilisé. Depuis la restriction du 2026-11-06, le périmètre est exclusivement XAU/USD : les autres symboles sont refusés par le code. Aucun ETF, indice ou futur n’a remplacé XAUUSD.

**Rapport historique et hors échantillon : BLOQUÉ.** Aucun nombre de trades de marché, taux de réussite, espérance, PnL ou courbe rentable publié. Les tests synthétiques ne sont jamais recyclés en rapport de performance. Les commandes sont prêtes pour un import vérifié et un préenregistrement réel.

## Simulation directe

L’adaptateur JSONL courant et le simulateur interne sont implémentés. Un essai court sans flux peut vérifier attente, arrêt borné et journal de santé ; il ne vérifie aucune réception de marché ni fraîcheur d’un fournisseur. Aucun processus de surveillance permanente n’est actif après les essais. Aucun compte démo ni compte réel connecté. Le projet refuse même les endpoints de démonstration à ce stade ; seule l’exécution interne est permise.

## Limites restantes

- Fournisseur de marché historique/courant et spécifications contractuelles réelles manquants. Calendrier et fermetures spécifiques ne sont pas validés automatiquement ; les gaps sont signalés sans inventer leur cause. Pour performance, le fournisseur et son calendrier doivent être documentés à l’import.
- Pas de carnet, ni de queue, de cotations intraminute, ni de remplissage partiel d’ordres. Les sorties partielles sont prises en charge ; ce n’est pas un modèle de liquidité réelle. Bid/ask OHLC ne révèlent pas leur synchronisation intrabougie ; spread intrabougie et financement sont approximatifs. Pas de conversion hors USD ; instrument bloqué plutôt que substitué.
- Pivots à fenêtres fixes et première cassure d’initialisation : interprétation de la structure, pas reproduction discrétionnaire. BOS à la formation, sweep, contacts et emboîtement sont enregistrés séparément ; flip offre/demande non implémenté. Aucun acteur institutionnel n’est supposé observé.
- Les extrêmes de sessions Gold complètes sont maintenant disponibles dans le contexte ; ils ne sont pas encore intégrés aux sweeps ; profils fixe/session précédente calculables par la primitive si la plage est fournie, sans filtre de stratégie actif. Horaires Gold de S6 non authentifiés. Sessions de rapport = tranches horaires NY de programmation, pas règles S6.
- M3 vérifie l’absence de FVG à clôture du CHoCH, pas sur une impulsion visuelle discrétionnaire. M6 est expérimental et limité à la continuation. Une occasion par zone/session est une hypothèse restrictive ; les occurrences manquées faute de confirmation sont journalisées mais un compteur exhaustif des « occasions qui auraient marché » n’est pas défini, pour éviter le recul rétrospectif.
- Recherche sans optimiseur ni apprentissage automatique. Walk-forward à paramètres figés et ablations préenregistrées, pas de grille exhaustive de seuils. La purge enlève les trades chevauchants des statistiques ; l’état financier reste continu et son effet est conservé. Pas de correction complète de tests multiples.
- L’interface recalcule les préfixes pour assurer la causalité ; coût croissant sur gros jeux. Elle affiche primitives/ordres/motifs mais n’est pas une plateforme graphique de courtage. La reprise recharge le journal complet ; compaction de long terme et supervision durable restent à configurer.

Chaque futur résultat de marché doit embarquer commit + hash code, version, paramètres complets, fournisseur, hash données, période, hypothèses d’exécution et commande. Une modification de stratégie crée une nouvelle expérience prospective et ne supprime jamais le passé.

## Spécialisation Gold v0.2.0

Ajout du Poste XAU/USD, des unités USD/once troy et contrat, de la cohérence point/onces, des marges en ticks, de l’ATR causal, des régimes descriptifs, des sessions avec DST, des extrêmes uniquement après session complète, des horaires fournisseur et fermetures planifiées, des protections spread/ATR/stop à décision et ouverture suivante. Calendrier USD manuel optionnel, vide et désactivé par défaut. Seuils du projet H11–H15, sans optimisation ni attribution à OlinVest. Rapport par session/régime sur futurs jeux de marché.

Les spécifications d’exemple et le calendrier fournisseur restent non vérifiés ; aucune collecte de données de marché n’a été ajoutée, aucune performance n’est mesurée. Les financements restent simplifiés. Voir `GOLD.md` et `gold-specialization-verification.json` pour le périmètre et la vérification de cette version.

Vérification v0.2.0 : 58 tests logiciels réussis et syntaxe JavaScript contrôlée. Le contrôle navigateur de cette nouvelle interface a été interrompu ; les anciens résultats Chromium et l’ancienne capture concernent la version antérieure. La nouvelle interface reste à vérifier dans un navigateur. Aucun processus durable n’est lancé.

## Audit indépendant0.3.0

Voir audit/REPORT.md et audit/verdicts.json : corrections par contradiction, référence24e2258 conservée, aucune mesure de marché, fidélité partielle par méthode. La parité nominale à bougies ne certifie pas la latence du flux actuel. Le serveur et le navigateur n’ont pas pu démarrer dans le sandbox ; les exports matplotlib ont été produits. Les anciens rapports et captures sont conservés et ne prouvent pas cette version.
