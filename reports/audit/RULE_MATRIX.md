# Registre indépendant des règles auditées

Les horodatages sont pris dans start_ms des segments récupérés, jamais reconstruits de mémoire. Les transcriptions sont automatiques et les images restent non vérifiées.

## A01 — M1
Contact seul insuffisant : attendre CHoCH LTF puis retracement de la nouvelle zone.

convention de programmation pour les seuils; noyau explicite dans les passages cités

Code : `lab/strategies.py Model.supply → Model.order → Broker.on_bar`
Paramètres actifs : H1/M5 ou H4/M15; attente30min; pivot corps≤0,5 / impulsion≥0,6
Tests : AuditOperations.test_m1_touch_without_choch_has_no_order, IntegrationTests.test_m1_end_to_end, AuditOperations.test_h4_m15_confirmation_path_executes_only_after_confirmation
- [S4 09:59.160](https://www.youtube.com/watch?v=0-4X_L8PeG4&t=599) : la hausse. Et si vous n'avez pas de change of caractère en low time frame, alors vous ne prenez pas de position. Une fois que vous avez trouvé votre change of caractère, alors vous avez deux setup et deux manières d'entrer en position avec cette stratégie. Si le change of caractère à la hausse laisse (explicite dans la transcription automatique; images non vérifiées)
- [S12 texte public](https://fr.tradingview.com/chart/XAUUSD/gHRfJT6R/) : PS: Aucunes confirmations en LTF je ne suis pas rentré sur cette zone (texte public relu; 26 novembre 2024; graphique non reconstruit)

## A02 — M1
Couples du plan Smart Money H1→M5 et H4→M15.

convention de programmation pour les seuils; noyau explicite dans les passages cités

Code : `lab/engine.py validate_config; Resampler; Model.supply`
Paramètres actifs : (60,5), (240,15)
Tests : AuditOperations.test_h4_m15_confirmation_path_executes_only_after_confirmation
- [S4 02:46.840](https://www.youtube.com/watch?v=0-4X_L8PeG4&t=166) : d'intérêt. Si vous étiez en train d'analyser en 4 heur time frame, vous allez descendre en 15 minutes time frame. Et si vous étiez en 1 heure time frame, alors vous descendez en 5 minutes time frame pour avoir plus de précision et venir prendre vos positions en utilisant des confirmation simple de dernière minute pour trouver des points (explicite dans la transcription automatique; images non vérifiées)

## A03 — primitives
Pivots disponibles après confirmation, aucune HTF incomplète utilisée.

convention de programmation, sans fenêtres numériques authentifiées dans les vidéos

Code : `lab/primitives.py Structure.push; lab/data.py Resampler.push`
Paramètres actifs : L=R=2 actifs; L=R=1 dans les fixtures; agrégations H4/D1 ancrées UTC, alignement OANDA/TradingView non vérifié
Tests : CausalityTests.test_pivot_invisible_until_confirmation, CausalityTests.test_htf_complete_and_gap

## A04 — zones
Pivot validé par clôture d’impulsion au-delà du high/low précédent; couleur opposée non universelle.

explicite pour clôture et couleur; convention pour corps, durée et géométrie de mèche

Code : `lab/primitives.py Structure.push`
Paramètres actifs : pivot/base/mèche distincts; corps0,5/0,6; TTL2880min
Tests : CausalityTests.test_zone_only_after_impulse
- [S5 11:34.480](https://www.youtube.com/watch?v=nOaffdm1eoU&t=694) : je vais même pouvoir trouver ma bougie pivot sur une bougie haussière qui s'est fait ensuite engloutir par une autre bougie haussière. Ce que je vais vraiment rechercher, c'est ce point pivot dans le prix qui a été causé juste avant d'envoyer ce mouvement agressif. C'est moment où le marché évolue comme (explicite dans la transcription automatique; images non vérifiées)
- [S5 11:52.440](https://www.youtube.com/watch?v=nOaffdm1eoU&t=712) : que dans une zone de dimen, la bougie d'impulsion doit toujours clôturer au-dessus du plus haut de la bougie précédente. Et pour une zone supply, elle doit clôturer en dessous du plus bas de la bougie précédente pour que la zone soit valide. Et tu peux le voir, la grosse différence entre ces deux (explicite dans la transcription automatique; images non vérifiées)

## A05 — sweeps
Dépassement puis réintégration bornée; distinguer formation et retest.

noyau qualitatif explicite; délai3 et réintégration par clôture sont des conventions

Code : `Structure.pending_sweeps / Structure.sweeps / Zone.formed_sweep; Model.supply last_sweep`
Paramètres actifs : délai≤3bougies; marge1tick; filtre optionnel
Tests : AuditRegressions.test_sweep_can_reintegrate_on_later_bar_within_bound, CausalityTests.test_persistent_break_is_not_sweep
- [S2 04:40.240](https://www.youtube.com/watch?v=0Xd8M0BkzCg&t=280) : amène à ce que l'on appelle un liquidity sweep ou un fake breakout. Le marché pousse au-dessus et stoppe tous ceux qui ont vendu la résistance et déclenche également tous ceux qui voulaient acheter le retest et la cassure. Ensuite, les gros acteurs peuvent se placer en vente de l'autre côté de tous (explicite dans la transcription automatique; images non vérifiées)

## A06 — M2
Sélectionner l’extrême connu, conserver l’objectif externe du parent, ne pas remplacer après échec.

convention de programmation pour les seuils; noyau explicite dans les passages cités

Code : `Model.supply family=M2; selection at parent.available_at`
Paramètres actifs : H4/H1/M30; D1/H4/H1; M30/M15/M5; limite30min; une sélection
Tests : IntegrationTests.test_m2_extreme_selection_without_choch, AuditOperations.test_m2_sell_selects_highest_known_child_and_ignores_future, AuditRegressions.test_m2_refinement_preserves_the_parent_external_target
- [S3 08:11.199](https://www.youtube.com/watch?v=kiXYHk37_mQ&t=491) : Quand tu as plusieurs zones, tu choisis ce qu'on appelle l'extrême zone. C'est la zone la plus éloignée du prix actuel dans cette nouvelle jambe haussière ou baissière qui a été créée ici. Notre jambe haussière va de ce point bas à ce point haut. C'est cette poussée bouliche haussière et on cherche un retracement pour rentrer à l'achat plus bas à l'intérieur de cette jambe haussière. Donc ici l'extrême zone c'est la zone la (explicite dans la transcription automatique; images non vérifiées)

## A07 — M3
Choisir la branche FVG ou sans-FVG au CHoCH, jamais après résultat.

condition source explicite; bornage de l’impulsion par pivot confirmé = convention

Code : `Model.supply impulse_fvgs and family=M3`
Paramètres actifs : FVG directionnels non invalidés et non complètement remplis depuis dernier pivot opposé confirmé
Tests : AuditRegressions.test_ote_cannot_ignore_a_fvg_earlier_in_same_impulse
- [S4 10:04.720](https://www.youtube.com/watch?v=0-4X_L8PeG4&t=604) : change of caractère, alors vous avez deux setup et deux manières d'entrer en position avec cette stratégie. Si le change of caractère à la hausse laisse derrière vous des niveaux de fer gap à récupérer ainsi qu'une zone de dimend, alors vous allez pouvoir rentrer avec un by limite avec un ratio risky reward de 1 pour de en mettant votre point d'entrée au niveau de votre zone de dimend avec un stop loss juste en dessous de celle-ci en pensant à bien intégrer votre spreads à votre point d'entrée pour aller chercher un rassurisky reward de 1 pour 2. Et c'est en fait au 1 pour 2 que vous allez (explicite dans la transcription automatique; images non vérifiées)
- [S4 10:54.920](https://www.youtube.com/watch?v=0-4X_L8PeG4&t=654) : aller chercher avec ces stratégies sera quand le marché ne vous donne pas de ferval gap après un change of caractère. À ce moment-là, vous allez simplement tracer un retracement de Fibonacci avec les mêmes paramètres que je vous mets sous vos yeux du point haut au point bas (explicite dans la transcription automatique; images non vérifiées)

## A08 — M3
Ancrages Fibonacci de l’impulsion LTF figés et milieu61,8–78,6%.

nombres dans ASR et contexte; image des ancrages non vérifiée, convention de pivot explicite

Code : `Model.supply anchors / anchor_pivot_id / branch_selected_at; fibonacci`
Paramètres actifs : profondeur0,702; end=max/min des LTF clôturées depuis pivot
Tests : AuditRegressions.test_ote_anchor_uses_the_ltf_impulse_not_last_m1_wick, IntegrationTests.test_fibonacci_fixed_convention
- [S4 11:08.000](https://www.youtube.com/watch?v=0-4X_L8PeG4&t=668) : venir chercher des entrées approximativement au milieu de la zone entre les 618 et les 786 de ce retracement de Fibonacci en appliquant la même stratégie que précédemment avec un rassuris reward de 1 pour 2 pour venir passer votre stop loss au point (explicite dans la transcription automatique; images non vérifiées)

## A09 — FVG
High[i-2]<low[i] ou low[i-2]>high[i], disponible après troisième clôture.

convention de programmation pour les seuils; noyau explicite dans les passages cités

Code : `Structure.push fvgs`
Paramètres actifs : inégalités strictes; remplissage borné[0,1]
Tests : CausalityTests.test_fvg_third_close_and_fill
- [S4 05:41.560](https://www.youtube.com/watch?v=0-4X_L8PeG4&t=341) : tout simplement un écart qui a été créé entre la première bougie d'un mouvement et la troisième bougie. En réalité, vous le voyez, c'est assez simple à identifier. C'est tout simplement quand la fervalue gap est haussière, quand le point haut de la première bougie ne touche pas le point bas de la troisième bougie. En réalité, entre ce point haut de la première bougie et le point bas de (explicite dans la transcription automatique; images non vérifiées)

## A10 — M4A
Range09:30–09:45 NY; biais HTF puis cassure/retest/confirmation.

ouverture M15 explicite; exécution M1 et fenêtre de cette adaptation non authentifiées dans S9

Code : `Model.opening family=M4A`
Paramètres actifs : 15M1 contiguës; confirmation M1 corps≥0,6; contexte obligatoire; fenêtre80min conventionnelle
Tests : AuditOperations.test_opr_m15_unavailable_before_0945
- [S9 00:24.720](https://www.youtube.com/watch?v=zORpvHHx0dM&t=24) : l'OP en réalité c'est très simple c'est tout simplement la première bougie d'ouverture en M 15 ou en M30 à 15h30 sur la session de New York et cette bougie elle va vous donner des niveaux très intéressants et très pertinents pour prendre des position sur la session de New York ici je vais vous donner l'exemple sur un indice US parce que (explicite dans la transcription automatique; images non vérifiées)

## A11 — M4B
Réintégration/rejet d’une borne; objectif borne opposée.

logique qualitative source; confirmation numérique = convention

Code : `Model.opening family=M4B`
Paramètres actifs : wick hors borne, clôture réintégrée, corps≥0,6; cible opposée
Tests : AuditOperations.test_opr_m15_unavailable_before_0945
- [S9 05:05.440](https://www.youtube.com/watch?v=zORpvHHx0dM&t=305) : le haut de l'OP soit comme vous le voyez ici on vient réintégrer l'OP par le bas et donc on attend tout simplement des bougies d'indécision sur le point bas de l'OP en faisant un pullback dessus pour rentrer en position et à minima venir chercher le point haut de l'OP et ici vous le voyez c'est exactement ce qui se (explicite dans la transcription automatique; images non vérifiées)

## A12 — M5A
Range09:30–09:35 NY; clôture hors range, retest et confirmation ultérieure.

convention de programmation pour les seuils; noyau explicite dans les passages cités

Code : `Model.opening → open_order family=M5A`
Paramètres actifs : 5M1; corps≥0,6 au-delà du retest; marché prochaine ouverture; cible2R prévue
Tests : IntegrationTests.test_m5a_end_to_end, CausalityTests.test_opr_only_at_end_and_dst
- [S10 05:20.960](https://www.youtube.com/watch?v=q7a9eXDsxYU&t=320) : ce que l'on attend, c'est simplement une bougie qui vienne clôturer à l'extérieur de notre range et ensuite on pourra parler des différentes entrées et même voir qu'est-ce que le displacement et pourquoi parfois il est important d'attendre cette confirmation avant de rentrer en position. Mais dans ces critères précis, on attend simplement (explicite dans la transcription automatique; images non vérifiées)
- [S10 05:58.000](https://www.youtube.com/watch?v=q7a9eXDsxYU&t=358) : minutes, le point bas. On casse vers le bas. Le prix remonte. Retest quelques bougies de rejet. Une bougie de confirmation. Et maintenant, on cherche simplement des entrées sur notre range 5 minutes avec notre stop juste au-dessus de la cassure et notre target a un minimum de 1 pour de rassuris reward (explicite dans la transcription automatique; images non vérifiées)

## A13 — M5B
Troisième bougie clôturée avec price action fort; exécution après décision.

décision troisième clôture explicite; force0,6 et première clôture intérieure = conventions, prix de clôture non garanti

Code : `Model.opening family=M5B; Broker.on_bar latency`
Paramètres actifs : milieu ET troisième bougie corps≥0,6; FVG; prix next bid/ask open
Tests : IntegrationTests.test_m5b_fvg_next_open, AuditRegressions.test_m5b_weak_third_candle_is_not_strong_confirmation
- [S10 09:23.959](https://www.youtube.com/watch?v=q7a9eXDsxYU&t=563) : rentre simplement à la clôture de cette troisème bougie. Ici, on a la première, la deuxè, la trisème. Une fois que le fervel du gap se forme et que la troisème bougie clôture et montre du price action fort, du réel momentum, c'est là que l'on peut rentrer à la clôture de la troisième bougie. Stop loss au même endroit que sur le break and retest sous le range en 5 minutes. Et on cherche là aussi un ratio risque (explicite dans la transcription automatique; images non vérifiées)

## A14 — M5
Divergence80/90minutes, convention figée avant test.

divergence explicitement constatée dans ASR

Code : `Model.opening elapsed; order expiry`
Paramètres actifs : 80min depuis09:30 NY, variantes90; aucune sélection automatique par volatilité
Tests : CausalityTests.test_opr_only_at_end_and_dst
- [S10 00:34.960](https://www.youtube.com/watch?v=q7a9eXDsxYU&t=34) : sur ces 5 premières minutes et de les trader seulement pendant les 80 minutes [musique] qui vont suivre cette ouverture de session. Et ce que j'aime particulièrement avec cette stratégie, c'est sa simplicité. Tu as une heure (explicite dans la transcription automatique; images non vérifiées)
- [S10 01:44.439](https://www.youtube.com/watch?v=q7a9eXDsxYU&t=104) : pouvoir utiliser pour structurer votre aide dans les 90 premières minutes après l'ouverture de New York ou même l'ouverture de n'importe quelle session. Et dans cette vidéo, vous allez apprendre exactement une stratégie de (explicite dans la transcription automatique; images non vérifiées)

## A15 — M6A
Sweep dans zone et englobement, pas simple changement de couleur.

qualitatif explicite; seuils et contexte HTF continuation/reversal = conventions expérimentales

Code : `Model.candles family=M6A`
Paramètres actifs : corps englobe corps précédent; direction requise; corps≥0,6; sweep depuis contact
Tests : IntegrationTests.test_all_variants_configured_and_run
- [S11 02:43.120](https://www.youtube.com/watch?v=Bw_1sO1Jzw0&t=163) : avec la bougie suivante qui vient nous faire une bougie englobante baissière avec l'entrée massive des vendeurs sur le marché et surtout des equal en ayant le même point haut que la bougie précédente. Ce qui nous valide ici un retournement après avoir récupéré cette byside liquidity. Et c'est à ce moment-là que vous avez une indication très puissante que votre tournement est validé avec un displacement baissier. Et (explicite dans la transcription automatique; images non vérifiées)

## A16 — M6B
Rejet après retracement puis confirmation directionnelle.

convention numérique; détail visuel non vérifié

Code : `Model.candles family=M6B`
Paramètres actifs : mèche distale≥0,5range puis clôture au-delà extrême; corps≥0,6
Tests : IntegrationTests.test_all_variants_configured_and_run
- [S11 08:06.960](https://www.youtube.com/watch?v=Bw_1sO1Jzw0&t=486) : bougie de réjection a un petit corps et une grande mèche en dessous de son corps. Ce qui nous indique en réalité que les vendeurs ont voulu vendre le prix à ce moment-là, mais que les acheteurs sont rentrés massivement sur le marché et ont complètement submergé les vendeurs et ont ravalé cette bougie. Juste après, vous attendez simplement (explicite dans la transcription automatique; images non vérifiées)

## A17 — M6C
Consolidation après CHoCH, cassure puis véritable reprise au retest.

convention numérique; retournement distinct ajouté expérimentalement, pas reproduction certifiée

Code : `Model.candles family=M6C`
Paramètres actifs : 3corps≤0,5; base après CHoCH; retest clôture du bon côté du niveau
Tests : AuditRegressions.test_m6_retest_below_broken_level_is_not_long_confirmation, AuditOperations.test_m6_reversal_context_is_explicit_and_not_continuation
- [S11 10:40.440](https://www.youtube.com/watch?v=Bw_1sO1Jzw0&t=640) : Et en réalité ici ce qu'on voit c'est que le prix est en train de consolider, d'accumuler et juste au-dessus on a un niveau de résistance qui va être intéressant à analyser. Ensuite on déroule un peu le prix pour voir qu'est-ce qui se passe et vous le voyez, on vient exploser ce niveau de résistance en l'ignorant complètement et en passant juste au-dessus. Et rappelez-vous, je vous l'ai toujours dit, on ne rentre jamais sur une impulsion. Et comme on a complètement (explicite dans la transcription automatique; images non vérifiées)

## A18 — sorties
Structurel,2R,3R ou minimum2,5R sont des politiques distinctes.

2R et2,5R localisés; 3R variante pédagogique S5 non universelle; politique choisie avant résultat

Code : `Model.order E1–E5`
Paramètres actifs : E1=structure; E2=2R; E3=3R; E5=min2,5R
Tests : AuditRegressions.test_fixed_r_exit_does_not_require_structural_target
- [S1 15:19.560](https://www.youtube.com/watch?v=paKplgt-KOA&t=919) : ratio risque et reward. Mais au minimum, je te conseille toujours d'avoir 2.5 de ratio risk reward sur chacune de tes positions, donc de gagner 250 pour 100 euros risqués. Mais le setup reste valide. Et si on regarde ce qui se passe, le trade reste gagnant, simplement parce qu'on suit la tendance. (explicite dans la transcription automatique; images non vérifiées)
- [S10 09:39.800](https://www.youtube.com/watch?v=q7a9eXDsxYU&t=579) : and retest sous le range en 5 minutes. Et on cherche là aussi un ratio risque et reward minimum de 1 pour de et c'est de cette simple manière que tu dois utiliser le deuxième modèle d'entrée avec une entrée légèrement plus agressive mais qui va des fois te (explicite dans la transcription automatique; images non vérifiées)
- [S5 22:05.080](https://www.youtube.com/watch?v=nOaffdm1eoU&t=1325) : reward fixe. Le principe est simple, tu vas toujours viser un pour deux ou un pour tr ou un pour 4 de ratio risque reward. Et ce que je te conseille si tu es débutant, c'est de viser toujours les trois de ratisky reward. Et c'est une approche qui va surtout t'aider dans tes débuts à mettre tes émotions de côté. Parce qu'en réalité sur ce type de position, tu vas même pas te poser la question de où est-ce que tu dois aller prendre tes profits. Soit ta zone t'envoie un mouvement assez agressif (explicite dans la transcription automatique; images non vérifiées)

## A19 — E4
Partiel et passage au prix d’entrée à2R, solde vers structure.

2R explicite; fraction50% et temporalité BE sur OHLC = conventions

Code : `Broker._take_partial / _close / _manage`
Paramètres actifs : fraction0,5 hypothèse; BE effectif prochaine bougie; quantités arrondies et frais de chaque jambe
Tests : AuditRegressions.test_half_at_two_r_then_entry_gives_one_r_gross, AuditRegressions.test_gap_over_partial_and_target_still_respects_quantities, ExecutionTests.test_partial_and_net_break_even
- [S4 10:34.399](https://www.youtube.com/watch?v=0-4X_L8PeG4&t=634) : stop loss au point d'entrée et que vous allez prendre une petite partie de vos profits. Et en réalité, juste après, vous allez attendre de récupérer l'ancien point haut dans une tendance haussière d'External liquidity qui est à récupérer dans ce mouvement en cours. Et vous allez pouvoir trouver ce niveau d'external liquidity, ce point haut du mouvement en cours en haut time frame pour vraiment aller chercher un maximum de profit. Le deuxième setup qu'on va (explicite dans la transcription automatique; images non vérifiées)

## A20 — exécution
Une sortie future intrabougie ne libère pas une position à l’ouverture précédente.

exactitude technique, aucune attribution à une vidéo

Code : `Broker.on_bar occupied_at_open`
Paramètres actifs : une position à l’ouverture, une entrée maximum par M1; ouvertures connues avant ambiguïtés
Tests : AuditRegressions.test_intrabar_exit_does_not_free_position_at_earlier_open, AuditRegressions.test_known_opening_target_precedes_a_later_stop

## A21 — instrument
Le fournisseur, son symbole et la devise du compte doivent être explicites.

schéma documenté; aucune requête API ni disponibilité du symbole sur un compte vérifiées

Code : `validate_instrument → manifest → Engine.spec → Broker.spec → snapshot → provenance UI`
Paramètres actifs : canonical XAUUSD; OANDA API XAU_USD; compte USD seulement; once troy/contrat explicites
Tests : AuditRegressions.test_canonical_label_does_not_allow_etf_provider_symbol, AuditRegressions.test_cad_account_cannot_be_silently_valued_in_usd
- [OANDA primitives texte public](https://developer.oanda.com/rest-live-v20/primitives-df/) : base currency and quote currency delimited by a “_” (documentation publique)

## A22 — Volume Profile
POC=bin de volume maximal; pas de profil futur.

POC explicite; approximation OHLC et VA70% conventions; volume réel non mesuré

Code : `volume_profile; aucun filtre branché par défaut`
Paramètres actifs : 32bins, VA70%, répartition uniforme OHLC; volume actuel absent
Tests : CausalityTests.test_no_future_volume_profile
- [S7 02:06.079](https://www.youtube.com/watch?v=nzo6dNkGg1w&t=126) : la zone de valeur basse, la VAL, et le plus important, le POC, cette ligne que vous voyez sur le volume profile depuis le début de cette vidéo qui est tout simplement le point of control. Et c'est en fait un point spécifique où il y a eu un pourcentage de transaction qui est généralement fixé à 70 % des transactions sur la plage définie par votre volume profile, plus simplement le niveau sur lequel il y a eu la majorité des transactions à l'intérieur de votre mouvement. Et en réalité, ça vous (explicite dans la transcription automatique; images non vérifiées)

## A23 — Gold sessions
Préparation matinale/Asie de S6 : fuseau non authentifié.

horaires S6 non vérifiés; fenêtres Gold du projet distinctes

Code : `GoldDesk : fenêtres de contexte du projet; pas filtre horaire S6 authentifié`
Paramètres actifs : sessions IANA observées; extrêmes seulement complets; aucun profil final futur
Tests : GoldCausalityTests.test_previous_session_is_invisible_until_complete, GoldCausalityTests.test_london_new_york_overlap_respects_different_dst_dates
- [S6 03:11.200](https://www.youtube.com/watch?v=QMlpPrxMV44&t=191) : chaque point de la stratégie. Chaque matin, entre 8h et 10h, je vais prendre un moment pour analyser les marchés et trouver mes niveaux d'intérêt en utilisant les trois sessions de marché. Et je vais t'expliquer pourquoi cette plage horaire. Ici, pour la stratégie, tu vas utiliser les trois sessions de marché et chaque matin, en réveillant, tu vas pouvoir trouver la liquidité qui s'est déversée sur la session asiade. Le setup qu'on va vouloir récupérer va être, comme je te (explicite dans la transcription automatique; images non vérifiées)

## A24 — direct
Le journal et le verrou d’incident persistent; stale suspend entrées et conserve protections.

exactitude technique, réception de marché actuelle non vérifiée

Code : `StreamingSession.ingest; Journal.restore/control; run_live`
Paramètres actifs : 90s par défaut, maximum300s; replay horloge virtuelle explicite
Tests : AuditOperations.test_halt_latch_survives_restart_and_keeps_position, AuditOperations.test_stale_feed_blocks_new_entries

## A25 — recherche
Inclure occasions non exécutées, stress cohérent et états de fenêtres sans futur.

protocole du projet; aucune évaluation de marché exécutée

Code : `opportunity_metrics; stress_bar; evaluate states[boundary]`
Paramètres actifs : budget120,3stress/modèle; comparaison54expériences; bootstrap1000journées graine17
Tests : AuditOperations.test_no_fill_counts_against_opportunity_denominator, AuditOperations.test_cost_stress_preserves_ohlc_envelope, AuditOperations.test_small_sample_is_not_called_a_method_failure
