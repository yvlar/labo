# Registre des sources et règles

Les 11 vidéos ont une transcription automatique française accessible. Les images vidéo n’ont pas été vérifiées. Les numéros de performance des titres ne constituent aucun critère de validation.

- [S1](https://www.youtube.com/watch?v=paKplgt-KOA) — La Seule Stratégie de Day Trading Dont Tu As Besoin (De Débutant à Pro) ; asr
- [S2](https://www.youtube.com/watch?v=0Xd8M0BkzCg) — Maîtriser les Liquidity Sweeps & Inducements (en 23 Minutes) ; asr
- [S3](https://www.youtube.com/watch?v=kiXYHk37_mQ) — La STRATÉGIE D’ENTRÉE PARFAITE Pour Multiplier Tes Résultats ; asr
- [S4](https://www.youtube.com/watch?v=0-4X_L8PeG4) — Plan de Trading Smart Money Ultra Complet (94% Win Rate?) ; asr
- [S5](https://www.youtube.com/watch?v=nOaffdm1eoU) — Comment Maîtriser les Supply & Demand Institutionnels (GUIDE ULTIME) ; asr
- [S6](https://www.youtube.com/watch?v=QMlpPrxMV44) — La Meilleure Stratégie de Trading sur le GOLD en 2026 (98% Win Rate?) ; asr
- [S7](https://www.youtube.com/watch?v=nzo6dNkGg1w) — Comment Je Gagne 1000€/Jour Grâce au Volume Profile (Stratégie Secrète) ; asr
- [S8](https://www.youtube.com/watch?v=8FTweNWh-oA) — FVG vs IMB - Quelle est la meilleure stratégie de trading ? ; asr
- [S9](https://www.youtube.com/watch?v=zORpvHHx0dM) — Trader L'OPR Tous Les Jours à 15h30 (91,91% Win Rate?) ; asr
- [S10](https://www.youtube.com/watch?v=q7a9eXDsxYU) — Ma STRATÉGIE de SCALPING M5 sur l’Open New York (Ultra Simple) ; asr
- [S11](https://www.youtube.com/watch?v=Bw_1sO1Jzw0) — Comment Entrer et Sortir d'un Trade Comme un Pro (Facilement) ; asr
- [S12](https://fr.tradingview.com/chart/XAUUSD/gHRfJT6R/) — texte public accessible ; texte public
- [S13](https://fr.tradingview.com/chart/XAUUSD/n9POswVQ/) — texte public accessible ; texte public
- [S14](https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/) — texte public accessible ; texte public

Le registre intégral machine lisible est `rules.json` : définition mathématique, paramètres, disponibilité, variantes, divergences et extraits horodatés.

## R01 — explicite
Retour zone HTF, confirmation de retournement LTF puis retracement de la nouvelle zone.
zone.active AND touched_at < CHoCH.available_at; entry_order après CHoCH; remplissage ultérieur.
Disponibilité : Clôture du CHoCH, puis cotation future
Divergences : Aucune divergence tranchée sans variante.

## R02 — explicite
Couples H1→M5 et H4→M15.
HTF=60,LTF=5 ou HTF=240,LTF=15.
Disponibilité : Clôtures complètes
Divergences : Aucune divergence tranchée sans variante.

## R03 — interprétation
Le sweep au retest est enregistré, filtre optionnel distinct.
wick au-delà de pivot confirmé + clôture de réintégration; persistent break exclu.
Disponibilité : Clôture de réintégration
Divergences : Ne pas confondre sweep à formation et au retest. Aucune obligation universelle ajoutée.

## R04 — interprétation
Structure haussière/baissière et CHoCH, représentés par pivots confirmés.
Extremum strict sur L+R+1 bougies; clôture au-delà du dernier pivot + marge; BOS si même direction, CHoCH si direction opposée; première cassure initialise la direction.
Disponibilité : pivot_time + R bougies clôturées
Divergences : La lecture discrétionnaire des grandes vagues n’est pas reproduite fidèlement par des fenêtres fixes.

## R05 — explicite
Zone pivot validée par clôture de l’impulsion au-delà de la bougie précédente.
Demande: close[i]>high[i-1]+m; offre: close[i]<low[i-1]-m; limites high/low du pivot. Pas de couleur opposée obligatoire.
Disponibilité : Clôture de i
Divergences : Aucune divergence tranchée sans variante.

## R06 — interprétation
Base, pivot et fractale de mèche restent des géométries distinctes.
Base = 3 bougies compactes puis clôture hors bornes; pivot = précédente; fractale = mèche distale précédente.
Disponibilité : Clôture de l’impulsion
Divergences : Les stratégies utilisent pivot par défaut. La mèche numérique est une approximation de l’affinement discrétionnaire.

## R07 — explicite
FVG haussier/baissier à trois bougies ; suivi du remplissage.
Bull: high[i-2]<low[i]; bear: low[i-2]>high[i]; fill borné [0,1].
Disponibilité : Après troisième clôture
Divergences : Aucune divergence tranchée sans variante.

## R08 — interprétation
Préférence de retour à Supply/Demand d’origine plutôt qu’entrée FVG systématique.
M1 entre sur pivot; FVG est caractéristique ou filtre explicite, jamais zone entrée implicite.
Disponibilité : Confirmation de la zone
Divergences : Le range de déplacement n’est pas un opening range. Passage précis de préférence à vérifier visuellement.

## R10 — explicite
Objectif structurel connu et stop derrière invalidation.
Cible = pivot HTF non cassé le plus proche au-delà de l’entrée, figé à décision; stop distale ±tick (ask pour short).
Disponibilité : Décision avant activation ordre
Divergences : Aucune divergence tranchée sans variante.

## R11 — explicite
Limite sur la sous-zone extrême, avec risque d’occasions manquées.
À activation HTF sélectionner parmi sous-zones déjà confirmées et emboîtées la plus basse en achat / plus haute en vente; aucune substitution après retest.
Disponibilité : Activation de la zone parent
Divergences : Affinement historique distinct de confirmation actuelle M1; génération exige données couvrant le parent.

## R12 — explicite
Branche OTE en absence de FVG après CHoCH.
Entrée=end-(end-start)*0.702; start=dernier pivot opposé confirmé; end=extrême du CHoCH, ancrages figés.
Disponibilité : Clôture CHoCH
Divergences : Absence de FVG mesurée sur clôture CHoCH; pas de branche de secours après perte. Nombres corroborés par le contexte mais non par images.

## R13 — interprétation
Discount/premium et OTE sont deux notions distinctes.
discount: midpoint(zone)<(last_high+last_low)/2; OTE = profondeur 61.8–78.6% d’une impulsion figée.
Disponibilité : Pivots confirmés au moment de mesure
Divergences : Aucune divergence tranchée sans variante.

## R20 — interprétation
OPR M15 avec contexte, cassure puis retest.
Range US 09:30–09:45 NY depuis 15 M1 complètes; biais HTF; clôture hors range, retest puis confirmation directionnelle au-delà de bougie retest.
Disponibilité : 09:45 New York puis confirmation
Divergences : Ancrage NY et seuils = conventions projet; 15h30 locale de la vidéo ne suffit pas à prouver le fuseau.

## R21 — interprétation
OPR M15 : réintégration/rejet, objectif borne opposée.
wick hors borne et clôture réintégrée directionnelle avec corps/range>=0.6; cible opposée figée.
Disponibilité : Clôture après construction complète
Divergences : Contexte observé sans obligation de biais dans la variante de rejet.

## R22 — interprétation
Range M5 construit 09:30–09:35 America/New_York.
5 M1 contiguës; max high/min low; pas de règle UTC fixe.
Disponibilité : 09:35 NY
Divergences : Les horaires locaux cités dans la vidéo ne sont pas utilisés comme fuseau universel.

## R23 — interprétation
M5A : clôture hors range, retest puis confirmation.
Break.close > upper+m ou <lower-m; bougie postérieure touche borne; autre bougie clôture au-delà de son extrême avec corps>=0.6.
Disponibilité : Clôture confirmation ; marché prochaine ouverture disponible
Divergences : Aucune divergence tranchée sans variante.

## R24 — explicite
M5B : déplacement et FVG, décision à troisième clôture.
FVG directionnel et clôture hors OPR; première bougie encore dedans, deuxième corps/range>=0.6; marché au prochain open bid/ask.
Disponibilité : Troisième clôture, exécution jamais rétroactive
Divergences : Le prix de clôture illustré n’est pas garanti exécutable ; code attend cotation ultérieure.

## R25 — explicite
Fenêtres 80/90 minutes et variantes de stop.
Fin des signaux = 09:30 NY + 80 min référence; 90 min variante. Stops : borne opposée, retest, confirmation.
Disponibilité : Fenêtre fixée avant test
Divergences : 80 minutes après ouverture et 90 premières minutes apparaissent dans la transcription. Convention de départ explicite, pas de choix selon résultats.

## R26 — explicite
Objectif fixe 2R OPR M5.
target=entry_reference+direction*2*abs(entry_reference-stop); cible figée avant fill.
Disponibilité : Décision
Divergences : Le R encaissé peut différer de 2 après gap, frais et arrondis.

## R30 — interprétation
Sweep dans une zone puis englobante, expérimental.
Sweep depuis contact + corps actuel englobe le corps précédent, direction HTF, corps/range>=0.6.
Disponibilité : Clôture LTF
Divergences : Continuation seule implémentée; contre-tendance non implémentée.

## R31 — interprétation
Rejet par mèche puis confirmation, expérimental.
Mèche distale précédente>=0.5 range; clôture suivante au-delà de son extrême, corps/range>=0.6.
Disponibilité : Clôture LTF
Divergences : Aucune divergence tranchée sans variante.

## R32 — interprétation
Cassure/retest de consolidation après CHoCH, expérimental.
CHoCH confirmé, base de 3 corps compacts, clôture de cassure, puis retest directionnel ultérieur.
Disponibilité : Clôture du retest confirmé
Divergences : Passages à affiner; ne constitue pas une transcription exacte du modèle visuel.

## R40 — explicite
Sortie structurelle, partiel et break-even à 2R.
À 2R sortir fraction initiale arrondie, stop au fill effectif à partir de bougie suivante; solde vers cible initiale.
Disponibilité : Atteinte de 2R, BE activé à la prochaine bougie
Divergences : 50% est hypothèse du projet. Break-even net peut être négatif après frais.

## R41 — explicite
3R pédagogique de S5, seuil minimum 2,5R de S1.
E3: cible fixe3R; E5: ne soumettre que si ratio structurel>=2.5.
Disponibilité : Avant entrée
Divergences : Aucune divergence tranchée sans variante.

## R42 — explicite
Risque 2–3% mentionné dans S4, non adopté.
Aucune application; le défaut projet est 0.25%.
Disponibilité : Sans effet moteur
Divergences : Mention à 14:22–14:38, transcription automatique ; non adoptée par le projet.

## R50 — explicite
POC et Value Area sur plage déjà terminée.
POC argmax V(bin); VA contiguë étendue depuis POC jusqu’à 70% de volume; uniformisation du volume M1 entre low/high.
Disponibilité : Toutes les bougies du profil doivent avoir end<=available_at
Divergences : Approximation OHLC, tick volume non global. Filtre non activé dans les modèles.

## R51 — non vérifié
Horaires Gold/Asie/Londres de S6 non authentifiés.
Aucun filtre de sessions S6 activé tant que fuseau des heures locales non vérifié.
Disponibilité : Bloqué
Divergences : Pas de conversion arbitraire de 15h30 ou de l’heure matinale.

## H01 — hypothèse
Primitives et durée de vie numériques.
Pivot L=R=2; m=0.01; égalité tolérance0.05; sweep<=3 bougies; zone expire 2880 minutes; clôture distale invalide.
Disponibilité : Après clôtures requises
Divergences : Tick/dimension des seuils doivent être adaptés par nouvel enregistrement, jamais sur test final.

## H02 — hypothèse
Risque et protections du projet, sans attribution à OlinVest.
Risque transaction0.25%; maximum ouvert0.5%; une position; perte quotidienne1%; pas de martingale.
Disponibilité : Avant chaque entrée
Divergences : Aucune divergence tranchée sans variante.

## H03 — hypothèse
Exécution conservatrice sur OHLC bid/ask M1.
Marché next open après latence; limite pénètre1tick; stop prioritaire si stop/cible touchés; gap stop au pire open + slippage; pas de profit cible sur bougie fill limite.
Disponibilité : Clôture M1 pour connaissance du fill; fill marché daté open
Divergences : Pas de carnet: volumes disponibles/queue, remplissages partiels d’ordres et spread intrabougie inconnus.

## H04 — hypothèse
Une occasion soumise par session OPR et par zone HTF.
Une zone utilisée ne redevient pas candidate; OPR.sent après soumission; mesure expirations/refus sans resélection.
Disponibilité : Soumission de l’ordre
Divergences : La vidéo montre parfois plusieurs occasions. Référence volontairement bornée, pas règle authentifiée.

## H05 — hypothèse
Choix de la cible et position de l’OTE figés.
Cible=plus proche pivot HTF non cassé; OTE extrême courant du CHoCH et dernier pivot opposé. Pas d’ancrage redessiné.
Disponibilité : Décision
Divergences : Aucune divergence tranchée sans variante.

## H06 — hypothèse
Paramètres M1 minimaux séparés du filtre FVG et du sweep.
M1 minimal sans obligation FVG ni sweep. Ablation isolée require_fvg ou require_sweep.
Disponibilité : Expérience préenregistrée
Divergences : Aucune divergence tranchée sans variante.

## H10 — hypothèse
Baseline comparable : cassure OPR simple.
Même OPR M5, même fenêtre 80 minutes, sans retest; stop borne opposée et cible2R; coûts/risque identiques.
Disponibilité : Clôture hors range puis prochaine ouverture
Divergences : Aucune divergence tranchée sans variante.
