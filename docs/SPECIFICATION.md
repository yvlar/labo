# Spécifications déterministes v0.1.0

Périmètre fixé au 2026-11-06 : XAU/USD exclusivement. `symbol` doit être exactement `XAUUSD`. Le contrôle commun refuse les autres symboles avant import, initialisation du simulateur, préenregistrement, évaluation ou lancement du flux. Les archives d’autres instruments sont conservées mais ne sont pas proposées dans l’interface. Les spécifications du fournisseur pour XAU/USD restent obligatoires ; cette restriction ne calibre aucun seuil et ne valide aucune performance.

## Temps et disponibilité

`Bar.time` = ouverture UTC, `Bar.end` = fin exclusive. Une M1 n’entre dans le moteur qu’après sa clôture. Les agrégations UTC M5/M15/M30/H1/H4/D1 exigent toutes leurs M1 contiguës ; aucune H4/D1 de session fournisseur n’est prétendue. Si nécessaire un autre ancrage doit créer une version distincte. Les OPR sont ancrés à 09:30 America/New_York avec transitions DST IANA ; affichage America/Toronto.

Les événements portent `seq`, `event_time`, `available_at`, instrument, stratégie, version et motifs/identifiants. Les pivots distinguent leur occurrence de leur confirmation. Les remplissages marché sont connus à fin de M1, avec `fill_time` = ouverture exécutée ; les financements datés à l’ouverture ne deviennent connus dans ce moteur à bougies qu’à la clôture. Aucune disponibilité n’est antidatée au pivot ou au prix d’entrée supposé.

## Ordre commun historique/direct

1. Valider M1 ; doublon identique idempotent, correction refusée. Détecter gap et annuler les ordres/confirmations en attente. Réinitialiser les fenêtres des primitives pour ne pas créer un FVG sur un trou.
2. Gérer la position existante : financement, stops, cible, partiel. Puis examiner les ordres créés précédemment, uniquement si `bar.time >= decision_at + latency`.
3. Marquer le capital au bid pour achat ou ask pour vente ; appliquer le blocage quotidien. Une seule nouvelle entrée par M1, une seule position simultanée.
4. Construire les HTF complètes, des plus grandes aux plus petites. Mettre à jour contacts et invalidations des objets déjà actifs. Confirmer pivots, BOS/CHoCH, sweeps, zones et FVG.
5. Exécuter les modèles par identifiant lexicographique stable ; décisions et ordres sont disponibles à cette clôture et n’entrent jamais dans la M1 déjà traitée.
6. Persister l’entrée et ses événements dans une transaction SQLite. Au redémarrage rejouer les entrées et vérifier l’égalité exacte du journal.

## Primitives et géométries

- Pivot strict sur L=R=2 par défaut ; égalités exclues des pivots. Comparaison au dernier pivot du même côté pour HH/LH ou HL/LL. Première cassure du dernier pivot confirmé initialise une direction ; les suivantes de même direction sont BOS et d’autre direction CHoCH. Cette initialisation est une hypothèse qui simplifie la lecture discrétionnaire. Sans cassure préalable, direction indéterminée ; les modèles de tendance attendent. M5 sans biais fonctionne malgré une structure HTF indéterminée.
- Cassure uniquement par clôture au-delà de marge 0,01. Variante par mèche non activée. Une cassure persistante n’est jamais comptée sweep. Le sweep des pivots est confirmé par réintégration dans ≤3 bougies ; un dépassement avec clôture extérieure est une cassure, pas un sweep.
- Égalités = deux pivots à distance ≤0,05, simple information. Le comptage des niveaux internes utilise les pivots non cassés entre prix et zone. Les extrêmes de sessions terminées ne sont pas encore des niveaux de sweep actifs.
- Zone pivot = high/low de dernière bougie au corps ≤50% avant impulsion au corps ≥60% et clôture au-delà de son extrême. Couleur non imposée. Base = trois bougies compactes puis impulsion hors bornes combinées. Fractale = mèche distale du pivot, distincte de sa zone complète. Les modèles choisissent `pivot` par défaut ; pas de mélange des géométries. Les quatre motifs Rally/Drop–Base–Rally/Drop utilisent le déplacement avant/après la base ; ce classement est une approximation.
- Activation à clôture de l’impulsion ; TTL 2 880 minutes ; invalidation par clôture de l’unité native au-delà de la borne distale ; contact = intersection après activation, nouveau contact après sortie ; profondeur maximale bornée [0,1]. Le journal du contact M1 du modèle est distinct du compteur de contacts sur l’unité native.
- FVG : `high[i-2] < low[i]` ou inverse baissier après clôture i ; remplissage par extrême, invalidation par clôture au-delà du bord distal.
- Fibonacci = `end-(end-start)*depth`. Ancrages conservés dans les raisons de l’ordre. Discount/premium du contexte utilise les derniers pivots connus ; ce n’est pas l’ancrage OTE du modèle M3.
- Volume Profile est une primitive hors filtre de stratégie : distribution uniforme par bougie entre low/high, 32 bins, VA contiguë depuis POC jusqu’à70%, tie-break vers prix bas. Interdit si bougie future ou volume absent. Pas de profil final de session courante appliqué au passé.

## Modèles

M1 : continuation HTF ; choisir la plus ancienne zone pivot valide touchée (disponibilité puis identifiant) ; premier contact admissible ; attendre CHoCH LTF **strictement après** contact, avec nouvelle zone pivot activée sur cette clôture. Entrée limite sur bord proximal, spread observé ajouté en achat ; stop distal et cible pivot HTF non cassé figés. Les versions FVG et sweep sont des filtres isolés ; le défaut minimal n’exige aucun des deux. Expiration de confirmation30min, ordre30min. Une seule tentative par zone ; les contacts ultérieurs restent mesurés sans relance automatique.

M2 : sélection figée à activation du parent, depuis zones confirmées et emboîtées, avec chaînes H4→H1→M30, D1→H4→H1, M30→M15→M5. Acheter la plus basse / vendre la plus haute parmi les derniers enfants valides. Aucun CHoCH requis. Les sous-zones doivent être contenues géométriquement et leur origine postérieure à celle du parent. Les chemins incomplets produisent une absence explicite, pas une sélection a posteriori.

M3 : même contexte de contact/CHoCH, mais uniquement si aucun FVG directionnel n’apparaît à cette clôture. Impulsion entre dernier pivot opposé confirmé et extrême du CHoCH, entrée à profondeur70,2%, stop derrière l’ancre, cible structurelle. La présence de FVG refuse cette branche avant tout résultat. L’absence de FVG sur une impulsion discrétionnaire plus large n’est pas reproduite.

M4A : range M15, biais HTF obligatoire, cassure/retest puis confirmation M1 au-delà de la bougie de retest. M4B : dépassement d’une borne, clôture réintégrée directionnelle, corps≥60%, cible borne opposée. Contexte mesurable mais non obligatoire pour B par défaut. Une occasion soumise par session.

M5A : range M5, clôture M1 extérieure, retest ultérieur, autre bougie directionnelle corps≥60% clôturant au-delà de l’extrême de retest. Le stop de retest utilise l’extrême de cette bougie ; il n’exige pas un pivot fractal confirmé supplémentaire. M5B : FVG directionnel sur trois M1, deuxième bougie au corps≥60%, première clôture encore du côté intérieur de la borne et troisième clôture extérieure. Décision à troisième clôture, marché au prochain open observé. Un stop de retest est interdit dans B puisqu’aucun retest n’y est requis ; seuls borne du range ou bougie de confirmation sont comparés. Contexte optionnel dans variante distincte. Fenêtre80min **depuis09:30**, variante90. Un ordre par session, pas de choix automatique M5/M15.

M6A/B/C : modèles de continuation HTF distincts, réservés à l’expérimentation. A=sweep+englobement des corps ; B=mèche précédente≥50% puis clôture directionnelle au-delà de son extrême ; C=CHoCH, base3bougies compactes, cassure puis retest directionnel. Corps de confirmation≥60%. Le volet contre-tendance n’est pas implémenté.

La baseline cassure simple partage instrument, OPR M5, fenêtre80min, budget de risque, coûts et cible2R. Aucun filtre de qualité combiné ou score à poids appris.

## Exécution, risque et sorties

Unité de quantité décrite par le fournisseur ; valeur du point exprimée en USD par unité. `qty=floor(budget/(distance_stop*point_value + commissions A/R + provision slippage)/qty_step)*qty_step`. Budget≤0,25% cash, marge requise=`qty*price*point_value*margin_rate`. Incrément/taille minimale et marge contrôlés. La position unique respecte un budget ouvert≤0,50% ; cette borne n’autorise pas une seconde position. Le risque effectif peut dépasser le budget après gap. Aucun mécanisme d’augmentation après perte.

Marché : ask open+slippage à l’achat, bid open−slippage à la vente. Limite : prix fixé, pénétration d’au moins1tick, pas d’amélioration favorable de gap. Un contact seul n’assure pas le fill. Latence en secondes : si open trop tôt, attendre la M1 suivante ; pas d’interpolation de cotation. Cible et stop sont connus avant exécution ; un gap qui les rend incohérents refuse l’ordre. Arrondis défavorables au tick, quantités arrondies vers le bas.

Stops : pire de stop et ouverture, puis slippage défavorable. Sur bougie stop+cible, stop prioritaire et ambiguïté comptée. Sur bougie d’entrée limite, aucun gain cible n’est garanti ; la cible attend la bougie suivante, mais stop reste actif. MAE/MFE en R sont des bornes de bougie entière, y compris avant remplissage intrabougie ; pas une mesure tick précise.

E1 structurel ; E2 cible2R ; E3 cible3R ; E4 cible structurelle au-delà de2R, partiel50% de quantité initiale arrondi à2R et stop au fill effectif à partir de M1 suivante ; E5 rejet si cible structurelle<2,5R. En E4, quantité insuffisante pour deux lots minimaux : partiel refusé et journalisé, aucun BE activé. Les commissions de chaque jambe et financement sont déduits ; R net=PnL net pondéré / risque de prix initial. Break-even au prix d’entrée n’implique pas net zéro.

États effectifs : contexte disponible → contact → confirmation attendue → ordre en attente → ouvert → partiellement fermé → fermé ; branches expirées/refusées/invalidées. M2 va directement de contexte à ordre limite. Les décisions d’attente explicitent les états qui n’ont pas généré de signal. Le journal d’événements est la source de vérité, pas un état graphique reconstruit avec le futur.
