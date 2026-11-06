# Audit indépendant du laboratoire XAU/USD — version0.3.0

## Conclusion

**Fidélité globale partielle pour toutes les méthodes ; performance de marché : données insuffisantes pour toutes.** Des noyaux publics sont retrouvés et plusieurs erreurs techniques ont été reproduites puis corrigées. Une fidélité partielle ne signifie ni perte ni gain de marché : aucune série réelle vérifiée n’a été testée. Les tests synthétiques ci-dessous valident le logiciel exclusivement.

Code contrôlé : `b2854027eaacc192382d43303f04cf76cb7f1ecf` ; hash `4e0f66c04ae9a061a75f80e696714f12dce95b72b1c73b1a7d168c07d161237c`. Référence avant corrections : `24e2258`. 86 tests logiciels passent.

## Référence et premier écart concret

`baseline/reference.json`, `baseline/active-configurations.json`, CSV bruts, manifestes, événements JSONL et journaux SQLite locaux conservent la référence avant correction. Les SQLite de tests sont locaux et exclus de Git ; leurs exports JSONL sont versionnés. Aucun journal prospectif de marché n’a été réécrit.

Le scénario M1 trace un ordre décidé07:40UTC puis exécuté sur retracement après décision. Le M5A trace une décision14:38UTC et une exécution à l’ouverture14:38, connue dans ce moteur à bougies à14:39. Les chiffres sont des dates de fixtures logicielles, pas des trades Gold observés. Les fixtures historiques existantes emploient pivots1/1 et désactivent les protections Gold ; M1H1 attend60min et le cas H4/M15 attend180min pour exercer les états. Ces valeurs de tests diffèrent des défauts actifs2/2, protections activées et attente30min. Elles sont archivées, pas choisies sur un résultat de marché.

Le premier défaut est conservé dans `baseline/M5-future-exit-reproducer-events.jsonl` : M5B sort avec le high de la minute14:40–14:41, puis M5A est exécuté rétroactivement à14:40. Cela libérait une position et du capital avant de connaître sa sortie. La réexécution CLI sur le même CSV conserve deux OPEN avant correction contre un seul après, dans causality-before-after.json; le deuxième est désormais refusé, sans modification des paramètres numériques. `occupied_at_open` empêche désormais cette nouvelle entrée. Une cible ou un partiel déjà franchi dès la première quote est en revanche traité avant les touches ultérieures ; un gap ne supprime plus le partiel E4.

## Instrument, unités et données

Les pages publiques relues indiquent OANDA:XAUUSD. La convention API OANDA est XAU_USD (BASE_QUOTE, documentation officielle archivée). Mais l’application n’a actuellement **aucun lecteur API de cours** : CSV/Parquet et fichier JSONL seulement. Il n’existe donc aucune requête fournisseur réelle à certifier. Le symbole, le fournisseur, le produit, la source, les unités et la devise sont des déclarations à l’import, protégées par empreintes ; les H4/D1 sont reconstruits avec ancrage UTC, sans alignement de session OANDA/TradingView authentifié ; un booléen verified ne prouve pas l’authenticité d’un fichier.

Les contrôles imposent XAU/USD en USD par once troy, quantités en contrats dont les onces sont explicites, valeur du point cohérente, bid/ask distincts, calendrier fournisseur sourcé et compte USD. CAD est bloqué, sans conversion fictive. GLD/GC/NQ ne passent pas sous provider_symbol. L’exemple de contrat reste non vérifié et ne désigne aucun compte OANDA. Les écarts avec un autre fournisseur ne sont pas mesurables sans deux séries réelles sur une même période.

Volume courant : absent faute de flux. La définition publique OANDA du volume de bougie est « number of prices created », pas un volume mondial de transactions. Le Volume Profile du code répartit uniformément le volume OHLC dans32bins : approximation, POC=bin maximal, VA70%, jamais un profil final futur. Aucun filtre de stratégie Volume Profile n’est actif. Les heures locales de S6 restent non authentifiées ; les sessions Gold IANA sont des conventions de contexte distinctes.

## Tableau des constats et corrections

| Modèle | Règle attendue | Comportement observé | Preuve | Écart | Correction | Résultat après correction |
|---|---|---|---|---|---|---|
| M1 | Contact→CHoCH→retracement, H1/M5 et H4/M15 | Séquence retrouvée dans le moteur et tracée depuis CSV; le simple contact ne trade pas | final-checked/M1-gain; final-checked/M1-no-confirmation; test H4/M15 | Pivots fixes et dernière zone de bougie sont des approximations; Gold ajoute des filtres projet | Moteur commun corrigé; pas de seuil optimisé | Séquence et non-trade vérifiés sur fixtures; fidélité globale partielle |
| M2 | Sous-zone extrême connue et même cible externe que parent | Extrême connu correct; cible recalculée pouvait devenir un pivot interne différent | baseline/m2-target-before.txt; test extrême achat/vente/futur | Cible100 au lieu150 dans le cas technique | Cible calculée depuis bord du parent avant exécution | Test passe; ordre limite peut rester non exécuté; performance indisponible |
| M3 | Brancher sur FVG de l’impulsion; sinon OTE61,8–78,6 figée | Avant : FVG uniquement de dernière clôture et extrême de dernière M1 | baseline/regression-before.txt; tests OTE | Mauvaise branche et mauvais ancrage M1/LTF | Impulsion LTF depuis pivot confirmé, extrême sur toutes ses bougies et FVG actifs connus | Cas corrigés passent; définition graphique du pivot reste conventionnelle |
| M4A/B | Range09:30–09:45 NY puis cassure/retest ou rejet vers borne opposée | Deux branches présentes, range absent avant09:45 | test_opr_m15_unavailable_before_0945; Model.opening | Exécution M1, corps0,6, une tentative/session et fenêtre80 sont conventions, pas S9 vérifié intégralement | Conventions exposées; aucun ajustement de résultat | Range causal vérifié; fidélité partielle et séquences de marché non reconstruites |
| M5A | Range5min→cassure→retest→confirmation; next quote | Chemin CSV→ordre14:38→fill open14:38 disponible14:39 dans scénario technique | final-checked/M5-retest; baseline/M5A-events.jsonl | Moteur pouvait réutiliser capital d’une sortie future intrabougie | Blocage si position déjà ouverte au début de la bougie | Régression corrigée; historique/rejeu identiques |
| M5B | FVG3bougies, troisième clôture forte, prix ultérieur, cible2R prévue | Next open correct; force de troisième bougie absente du contrôle initial | baseline/m5-third-before.txt; final-checked/M5-fvg-gap | Une troisième bougie faible déclenchait quand même | Direction et corps0,6 à troisième bougie, même seuil déjà déclaré; ouverture réelle suivante | Faible bougie refusée; gap exécuté au prochain ask/bid, jamais clôture garantie |
| M6A/B/C | Définitions numériques, continuation et retournement séparés | A/B quantifiés; C pouvait acheter en clôturant encore sous le niveau cassé | baseline/regression-before.txt; tests M6 retest et contexte | M6C confirmation erronée; retournement initialement absent | Clôture côté correct et base après CHoCH; context_mode distinct expérimental | Régression passe; fidélité visuelle complète non vérifiée |
| E1–E5 | Politiques distinctes, quantités réelles et frais | E2/E3 demandaient par erreur une cible structurelle; gap E4 pouvait ignorer le partiel | baseline/regression-before.txt; baseline/partial-gap-before.txt | Rejets injustifiés ou résultat brut incorrect en gap | Cible fixe calculée avant test de cible; partiel à ouverture connue avant solde | Moitié2R+moitiéBE=1R brut; gaps partiels pondérés correctement |
| Commun | Pivots/zones/FVG causaux, sweeps bornés | Confirmations causales; sweep retardé perdu dès première clôture extérieure | tests disponibilité; baseline/regression-before.txt | Sweep à réintégration suivante absent | Pending sweep borné, sans réécrire la cassure de structure passée | Persistant non sweep; réintégration bornée nouvel événement |
| Commun | Instrument réel et compte correctement identifiés | Pas d’API de données; import déclaratif; devise compte CAD ignorée | baseline/regression-before.txt; gold-status; live-current-attempt.txt | Étiquette seule ne prouve aucune source; USD/CAD non implémenté | provider_symbol et account_currency explicites, CAD et symboles ETF/futurs refusés | Contrôles locaux passent; flux OANDA effectif reste non vérifiable |
| Direct | Redémarrage, doublon, gap, données périmées | Idempotence présente; latch HALTED oublié après restart | test_halt_latch_survives_restart_and_keeps_position | Reprise pouvait perdre l’arrêt opérationnel | Latch SQLite persistant; protections conservées, empreinte du flux chaînée | Rejeu/stream commun identique; aucun flux actuel reçu |
| Recherche | Résultats par fenêtre, occasion et coûts cohérents | Ancien état final répété par fenêtre; stress ask pouvait casser OHLC; occasions absentes | stress_bar, opportunity_metrics, evaluate diff; tests comptables | Présentation temporelle et dénominateur incomplets | États par frontière, enveloppe OHLC, cohortes avec non-fill et censures, minimum échantillon avant verdict | Tests logiciels passent; génération positive de rapport marché encore non exercée |

## Verdicts séparés

| Méthode | Fidélité | Exactitude technique locale | Évaluation de marché |
|---|---|---|---|
| M1 | partiel | Parcours H1/M5 et H4/M15 et contact sans CHoCH testés; géométrie discrétionnaire non certifiée | données insuffisantes |
| M2 | partiel | Sélection achat/vente, exclusion du futur et cible parent testées; pas de reconstruction brute M2 de marché | données insuffisantes |
| M3 | partiel | Tests de branche FVG et ancrages LTF; pas de reconstruction brute de marché | données insuffisantes |
| M4A | partiel | Range causal testé; séquence de confirmation contrôlée dans code, sans cas brut de marché | données insuffisantes |
| M4B | partiel | Range causal testé; rejet numérique présent, sans cas brut de marché | données insuffisantes |
| M5A | partiel | Parcours CLI complet, quote ultérieure, reprise et régression intrabougie testés | données insuffisantes |
| M5B | partiel | Parcours CLI complet avec gap et bougie faible refusée; arrivée réelle du flux non validée | données insuffisantes |
| M6A | partiel | Conditions numériques et mode de contexte exécutables; fidélité et trajectoire brute complète non certifiées | données insuffisantes |
| M6B | partiel | Conditions numériques exécutables; fidélité et trajectoire brute complète non certifiées | données insuffisantes |
| M6C | partiel | Régression de retest corrigée; contextes séparés, branche expérimentale | données insuffisantes |

M1 conserve une structure à pivots fixes et une zone pivot de la bougie précédant la clôture de CHoCH : ce n’est pas une reproduction visuelle discrétionnaire complète. M2 sélectionne à l’activation du parent, sans redessiner ensuite. M3 fige la branche sur les FVG encore actifs de l’impulsion ancrée au dernier pivot opposé confirmé. M4 utilise une exécution M1 et des seuils de programmation qui ne sont pas tous authentifiés par S9. M5 respecte le range et le next quote, mais ajoute des filtres numériques et un seul ordre par session. M6 a désormais des modes continuation/reversal séparés dans la configuration d’audit ; leur contexte HTF est une hypothèse expérimentale, sans certification visuelle. Les seuils Gold obligatoires de primary/variants sont des ajouts du projet H11–H15, pas des règles OlinVest.

## Épreuves réellement réalisées

- Invariance par plusieurs préfixes, données futures supprimées et modifiées : événements, snapshots et objets connus comparés. Les variantes existantes sont aussi couvertes par la suite unitaire.
- Parité : même StreamingSession.ingest que live, avec une horloge virtuelle à clôture+1seconde clairement étiquetée REJEU EN FLUX. Ce n’est pas une connexion de marché actuelle. received_at contrôle la fraîcheur mais ne décale pas les available_at nominaux du moteur : la latence réelle et la première cotation accessible après arrivée restent non vérifiées. Réconciliation des événements et positions, redémarrage et doublons.
- Incidents : flux ancien, donnée future/corrigée, gap, redémarrage sous verrou, position conservée et protections continuées. Le latch SQLite persiste maintenant.
- Comptabilité : moitié2R/moitiéentrée=1R brut ; commissions de toutes jambes ; stop au prix d’entrée peut perdre net ; gaps et partiels à ouverture connue ; dimensionnement et marge.
- Visualisations : `final-checked/*/visual/decision.png` et `after.png`, plus les manifestes. Premier événement de chaque fixture indépendante de gain, perte, absence, non-fill et ambiguïté ; pas une sélection d’exemples de marché. Les zones ne sont tracées qu’après leur disponibilité.
- Application : commandes import-data, verify-engine, export-decision, gold-status, refus synthétique de history/preregister, tentative live normale et probe2secondes exécutées. Le serveur HTTP normal est bloqué par le sandbox à socket.socket(EPERM) ; Chromium n’a pas démarré. Le navigateur de cette version reste donc non vérifié.

La publication S12 est datée26novembre2024 et contient bien le post-scriptum sans confirmation/sans entrée. Date et texte connus ne suffisent pas : limites précises de zone, fuseau du graphique et série M1 correspondante n’ont pas été reconstruits. Le cas aucun-trade est volontairement technique. Les images des11vidéos n’ont pas été vérifiées ; les nombres ASR sensibles restent signalés dans le registre.

## Performance et protocole

Aucune métrique financière de marché publiée : occasions, trades, espérance, drawdown, frais, séries de pertes et sensibilité sont tous **non mesurés** sur XAU/USD réel. Les transactions des fixtures sont uniquement des preuves de comptabilité et de causalité. Les cas ambiguës portent des bornes nettes de scénarios d’ordre intrabougie ; dans la fixture dédiée, le stop prioritaire est retenu. Aucun impact statistique de ces ambiguïtés sur le Gold réel n’est connu.

`configs/audit-comparisons.json` préenregistre18modèles,54simulations au coût×1/×2/×3 dans budget120 : M1/direct même parent, M1/sweep, M2/parent, M5A/M5B/cassure simple, E4/sortieunique, M6 continuation/reversal. Les paires E4/sortieunique ont un filtre structurel commun strictement supérieur à2R pour éviter de confondre effet de sortie et éligibilité. Les occasions partagées sont identifiées, les non-fill et censures comptés. Les états de compte sont maintenant pris à la fin de chaque fenêtre, pas à la fin du test global. Le stress OHLC conserve une enveloppe ask cohérente et reste une approximation.

Aucun seuil des méthodes n’a été réglé sur un résultat de marché. Les corrections changent la version et exigent une nouvelle expérience prospective. Les données déclarées incomplètes par le fournisseur sont maintenant refusées même si leur date est passée; en absence de ce drapeau, le CSV est seulement attesté final par son exporteur. Les paramètres et spécifications sont copiés pour empêcher une mutation externe silencieuse après initialisation. Les anciennes dates de splits sont des exemples, pas un test final effectivement réservé. Après obtention du jeu réel, figer coûts, dates et configurations avant évaluation ; ne pas élire les paramètres avec le test final. Le bootstrap journalier est implémenté mais aucun walk-forward de marché ni intervalle d’incertitude de marché n’a été exécuté. La recherche actuelle est à paramètres fixes, sans entraînement ni optimisation automatique.

## Reproduction et étapes bloquantes

Voir `REPRODUCE.md` pour les cinq points d’entrée et `final-checked/commands.json` pour les21commandes exactes déjà exécutées avec leurs codes de sortie. Voir `rules-audited.json` pour sources, horodatages issus des segments, paramètres et tests. `tests-final.txt` est le journal de tests.

Étape manquante précise : fournir un export réel XAU/USD M1 bid/ask et ses métadonnées vérifiées (symbole fournisseur effectif, contrat, tick, compte, calendrier et provenance). L’import pourra alors être lancé, puis le préenregistrement avec un découpage réel et un test final intact. Pour le direct, un exporteur autorisé doit alimenter des M1 clôturées actuelles ; aucun fichier ni identifiant n’est présent ici. Aucune comparaison fournisseur, performance historique/OOS ou réception actuelle ne peut être certifiée avant cela. Aucun ordre réel, aucun processus permanent lancé.
