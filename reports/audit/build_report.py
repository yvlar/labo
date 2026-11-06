"""Rebuild the evidence index from archived public captions and actual software-test outputs."""
import hashlib
import json
import re
from pathlib import Path
from lab.data import canonical,digest
from lab.research import revision

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/audit'
video_files=[ROOT/'docs/sources/retrieval-0.json',ROOT/'docs/sources/retrieval-4.json']
videos=sum((json.loads(p.read_text())['data']['alexandria'] for p in video_files),[])

def source(number,pattern,minimum=0,count=7):
    d=videos[number-1]['data'];segments=d['segments']
    found=next((i for i,s in enumerate(segments) if s['start_ms']>=minimum and re.search(pattern,s['text'],re.I)),None)
    if found is None:return {'id':f'S{number}','status':'non vérifié : passage non localisé','url':d['url']}
    group=segments[max(0,found-1):found+count]
    ms=group[0]['start_ms'];seconds=ms//1000
    return {'id':f'S{number}','status':'explicite dans la transcription automatique; images non vérifiées',
        'url':d['url']+'&t='+str(seconds),'start_ms':ms,'timestamp':f'{seconds//60:02}:{seconds%60:02}.{ms%1000:03}',
        'quote':' '.join(s['text'] for s in group),'caption_kind':d['kind']}

rules=[]
def rule(id,model,expected,refs,code,params,tests,status='convention de programmation pour les seuils; noyau explicite dans les passages cités'):
    rules.append({'rule_id':id,'model':model,'expected':expected,'sources':refs,'translation_status':status,
        'code':code,'active_parameters':params,'tests':tests})

rule('A01','M1','Contact seul insuffisant : attendre CHoCH LTF puis retracement de la nouvelle zone.',
     [source(4,'change of caractère',590000),{'id':'S12','url':'https://fr.tradingview.com/chart/XAUUSD/gHRfJT6R/',
       'quote':'PS: Aucunes confirmations en LTF je ne suis pas rentré sur cette zone','status':'texte public relu; 26 novembre 2024; graphique non reconstruit'}],
     'lab/strategies.py Model.supply → Model.order → Broker.on_bar','H1/M5 ou H4/M15; attente30min; pivot corps≤0,5 / impulsion≥0,6',
     ['AuditOperations.test_m1_touch_without_choch_has_no_order','IntegrationTests.test_m1_end_to_end','AuditOperations.test_h4_m15_confirmation_path_executes_only_after_confirmation'])
rule('A02','M1','Couples du plan Smart Money H1→M5 et H4→M15.',[source(4,'4 heur time frame',160000,8)],
     'lab/engine.py validate_config; Resampler; Model.supply','(60,5), (240,15)', ['AuditOperations.test_h4_m15_confirmation_path_executes_only_after_confirmation'])
rule('A03','primitives','Pivots disponibles après confirmation, aucune HTF incomplète utilisée.',[],
     'lab/primitives.py Structure.push; lab/data.py Resampler.push','L=R=2 actifs; L=R=1 dans les fixtures; agrégations H4/D1 ancrées UTC, alignement OANDA/TradingView non vérifié',
     ['CausalityTests.test_pivot_invisible_until_confirmation','CausalityTests.test_htf_complete_and_gap'],'convention de programmation, sans fenêtres numériques authentifiées dans les vidéos')
rule('A04','zones','Pivot validé par clôture d’impulsion au-delà du high/low précédent; couleur opposée non universelle.',
     [source(5,'bougie haussière',690000),source(5,'clôturer',710000)],'lab/primitives.py Structure.push','pivot/base/mèche distincts; corps0,5/0,6; TTL2880min',
     ['CausalityTests.test_zone_only_after_impulse'],'explicite pour clôture et couleur; convention pour corps, durée et géométrie de mèche')
rule('A05','sweeps','Dépassement puis réintégration bornée; distinguer formation et retest.',[source(2,'fake breakout',270000)],
     'Structure.pending_sweeps / Structure.sweeps / Zone.formed_sweep; Model.supply last_sweep', 'délai≤3bougies; marge1tick; filtre optionnel',
     ['AuditRegressions.test_sweep_can_reintegrate_on_later_bar_within_bound','CausalityTests.test_persistent_break_is_not_sweep'],
     'noyau qualitatif explicite; délai3 et réintégration par clôture sont des conventions')
rule('A06','M2','Sélectionner l’extrême connu, conserver l’objectif externe du parent, ne pas remplacer après échec.',
     [source(3,'extrême zone',490000,10)],'Model.supply family=M2; selection at parent.available_at',
     'H4/H1/M30; D1/H4/H1; M30/M15/M5; limite30min; une sélection',
     ['IntegrationTests.test_m2_extreme_selection_without_choch','AuditOperations.test_m2_sell_selects_highest_known_child_and_ignores_future','AuditRegressions.test_m2_refinement_preserves_the_parent_external_target'])
rule('A07','M3','Choisir la branche FVG ou sans-FVG au CHoCH, jamais après résultat.',[source(4,'deux setup',600000,15),source(4,'quand le marché ne vous donne',650000,6)],
     'Model.supply impulse_fvgs and family=M3','FVG directionnels non invalidés et non complètement remplis depuis dernier pivot opposé confirmé',
     ['AuditRegressions.test_ote_cannot_ignore_a_fvg_earlier_in_same_impulse'],'condition source explicite; bornage de l’impulsion par pivot confirmé = convention')
rule('A08','M3','Ancrages Fibonacci de l’impulsion LTF figés et milieu61,8–78,6%.',[source(4,'milieu',660000,6)],
     'Model.supply anchors / anchor_pivot_id / branch_selected_at; fibonacci','profondeur0,702; end=max/min des LTF clôturées depuis pivot',
     ['AuditRegressions.test_ote_anchor_uses_the_ltf_impulse_not_last_m1_wick','IntegrationTests.test_fibonacci_fixed_convention'],
     'nombres dans ASR et contexte; image des ancrages non vérifiée, convention de pivot explicite')
rule('A09','FVG','High[i-2]<low[i] ou low[i-2]>high[i], disponible après troisième clôture.',[source(4,'première bougie',340000,9)],
     'Structure.push fvgs','inégalités strictes; remplissage borné[0,1]', ['CausalityTests.test_fvg_third_close_and_fill'])
rule('A10','M4A','Range09:30–09:45 NY; biais HTF puis cassure/retest/confirmation.',[source(9,'première bougie',20000,8)],
     'Model.opening family=M4A','15M1 contiguës; confirmation M1 corps≥0,6; contexte obligatoire; fenêtre80min conventionnelle',
     ['AuditOperations.test_opr_m15_unavailable_before_0945'],'ouverture M15 explicite; exécution M1 et fenêtre de cette adaptation non authentifiées dans S9')
rule('A11','M4B','Réintégration/rejet d’une borne; objectif borne opposée.',[source(9,'réintégrer',290000,7)],
     'Model.opening family=M4B','wick hors borne, clôture réintégrée, corps≥0,6; cible opposée',
     ['AuditOperations.test_opr_m15_unavailable_before_0945'],'logique qualitative source; confirmation numérique = convention')
rule('A12','M5A','Range09:30–09:35 NY; clôture hors range, retest et confirmation ultérieure.',[source(10,'clôturer à l’extérieur|clôturer à l\'extérieur',310000,8),source(10,'Retest',350000,7)],
     'Model.opening → open_order family=M5A','5M1; corps≥0,6 au-delà du retest; marché prochaine ouverture; cible2R prévue',
     ['IntegrationTests.test_m5a_end_to_end','CausalityTests.test_opr_only_at_end_and_dst'])
rule('A13','M5B','Troisième bougie clôturée avec price action fort; exécution après décision.',[source(10,'troisème bougie',560000,10)],
     'Model.opening family=M5B; Broker.on_bar latency','milieu ET troisième bougie corps≥0,6; FVG; prix next bid/ask open',
     ['IntegrationTests.test_m5b_fvg_next_open','AuditRegressions.test_m5b_weak_third_candle_is_not_strong_confirmation'],
     'décision troisième clôture explicite; force0,6 et première clôture intérieure = conventions, prix de clôture non garanti')
rule('A14','M5','Divergence80/90minutes, convention figée avant test.',[source(10,'80 minutes',0,5),source(10,'90 premières',0,5)],
     'Model.opening elapsed; order expiry','80min depuis09:30 NY, variantes90; aucune sélection automatique par volatilité',
     ['CausalityTests.test_opr_only_at_end_and_dst'],'divergence explicitement constatée dans ASR')
rule('A15','M6A','Sweep dans zone et englobement, pas simple changement de couleur.',[source(11,'englobante',150000,10)],
     'Model.candles family=M6A','corps englobe corps précédent; direction requise; corps≥0,6; sweep depuis contact',
     ['IntegrationTests.test_all_variants_configured_and_run'],'qualitatif explicite; seuils et contexte HTF continuation/reversal = conventions expérimentales')
rule('A16','M6B','Rejet après retracement puis confirmation directionnelle.',[source(11,'grande mèche',480000,8)],
     'Model.candles family=M6B','mèche distale≥0,5range puis clôture au-delà extrême; corps≥0,6',
     ['IntegrationTests.test_all_variants_configured_and_run'],'convention numérique; détail visuel non vérifié')
rule('A17','M6C','Consolidation après CHoCH, cassure puis véritable reprise au retest.',[source(11,'consolider',620000,12)],
     'Model.candles family=M6C','3corps≤0,5; base après CHoCH; retest clôture du bon côté du niveau',
     ['AuditRegressions.test_m6_retest_below_broken_level_is_not_long_confirmation','AuditOperations.test_m6_reversal_context_is_explicit_and_not_continuation'],
     'convention numérique; retournement distinct ajouté expérimentalement, pas reproduction certifiée')
rule('A18','sorties','Structurel,2R,3R ou minimum2,5R sont des politiques distinctes.',[source(1,'2.5',900000),source(10,'ratio risque',580000,6),source(5,'un pour|débutant',1310000,12)],
     'Model.order E1–E5','E1=structure; E2=2R; E3=3R; E5=min2,5R',
     ['AuditRegressions.test_fixed_r_exit_does_not_require_structural_target'],'2R et2,5R localisés; 3R variante pédagogique S5 non universelle; politique choisie avant résultat')
rule('A19','E4','Partiel et passage au prix d’entrée à2R, solde vers structure.',[source(4,'petite partie',630000,11)],
     'Broker._take_partial / _close / _manage','fraction0,5 hypothèse; BE effectif prochaine bougie; quantités arrondies et frais de chaque jambe',
     ['AuditRegressions.test_half_at_two_r_then_entry_gives_one_r_gross','AuditRegressions.test_gap_over_partial_and_target_still_respects_quantities','ExecutionTests.test_partial_and_net_break_even'],
     '2R explicite; fraction50% et temporalité BE sur OHLC = conventions')
rule('A20','exécution','Une sortie future intrabougie ne libère pas une position à l’ouverture précédente.',[],
     'Broker.on_bar occupied_at_open','une position à l’ouverture, une entrée maximum par M1; ouvertures connues avant ambiguïtés',
     ['AuditRegressions.test_intrabar_exit_does_not_free_position_at_earlier_open','AuditRegressions.test_known_opening_target_precedes_a_later_stop'],
     'exactitude technique, aucune attribution à une vidéo')
rule('A21','instrument','Le fournisseur, son symbole et la devise du compte doivent être explicites.',
     [{'id':'OANDA primitives','url':'https://developer.oanda.com/rest-live-v20/primitives-df/','quote':'base currency and quote currency delimited by a “_”'}],
     'validate_instrument → manifest → Engine.spec → Broker.spec → snapshot → provenance UI',
     'canonical XAUUSD; OANDA API XAU_USD; compte USD seulement; once troy/contrat explicites',
     ['AuditRegressions.test_canonical_label_does_not_allow_etf_provider_symbol','AuditRegressions.test_cad_account_cannot_be_silently_valued_in_usd'],
     'schéma documenté; aucune requête API ni disponibilité du symbole sur un compte vérifiées')
rule('A22','Volume Profile','POC=bin de volume maximal; pas de profil futur.',[source(7,'POC',120000,12)],
     'volume_profile; aucun filtre branché par défaut','32bins, VA70%, répartition uniforme OHLC; volume actuel absent',
     ['CausalityTests.test_no_future_volume_profile'],'POC explicite; approximation OHLC et VA70% conventions; volume réel non mesuré')
rule('A23','Gold sessions','Préparation matinale/Asie de S6 : fuseau non authentifié.',[source(6,'Chaque matin',190000,12)],
     'GoldDesk : fenêtres de contexte du projet; pas filtre horaire S6 authentifié','sessions IANA observées; extrêmes seulement complets; aucun profil final futur',
     ['GoldCausalityTests.test_previous_session_is_invisible_until_complete','GoldCausalityTests.test_london_new_york_overlap_respects_different_dst_dates'],
     'horaires S6 non vérifiés; fenêtres Gold du projet distinctes')
rule('A24','direct','Le journal et le verrou d’incident persistent; stale suspend entrées et conserve protections.',[],
     'StreamingSession.ingest; Journal.restore/control; run_live','90s par défaut, maximum300s; replay horloge virtuelle explicite',
     ['AuditOperations.test_halt_latch_survives_restart_and_keeps_position','AuditOperations.test_stale_feed_blocks_new_entries'],
     'exactitude technique, réception de marché actuelle non vérifiée')
rule('A25','recherche','Inclure occasions non exécutées, stress cohérent et états de fenêtres sans futur.',[],
     'opportunity_metrics; stress_bar; evaluate states[boundary]','budget120,3stress/modèle; comparaison54expériences; bootstrap1000journées graine17',
     ['AuditOperations.test_no_fill_counts_against_opportunity_denominator','AuditOperations.test_cost_stress_preserves_ohlc_envelope','AuditOperations.test_small_sample_is_not_called_a_method_failure'],
     'protocole du projet; aucune évaluation de marché exécutée')
(OUT/'rules-audited.json').write_text(canonical({'sources_are_public':True,'videos_are_auto_captions':True,'video_images_verified':False,'rules':rules}))

rows=[
 ('M1','Contact→CHoCH→retracement, H1/M5 et H4/M15','Séquence retrouvée dans le moteur et tracée depuis CSV; le simple contact ne trade pas','final-checked/M1-gain; final-checked/M1-no-confirmation; test H4/M15','Pivots fixes et dernière zone de bougie sont des approximations; Gold ajoute des filtres projet','Moteur commun corrigé; pas de seuil optimisé','Séquence et non-trade vérifiés sur fixtures; fidélité globale partielle'),
 ('M2','Sous-zone extrême connue et même cible externe que parent','Extrême connu correct; cible recalculée pouvait devenir un pivot interne différent','baseline/m2-target-before.txt; test extrême achat/vente/futur','Cible100 au lieu150 dans le cas technique','Cible calculée depuis bord du parent avant exécution','Test passe; ordre limite peut rester non exécuté; performance indisponible'),
 ('M3','Brancher sur FVG de l’impulsion; sinon OTE61,8–78,6 figée','Avant : FVG uniquement de dernière clôture et extrême de dernière M1','baseline/regression-before.txt; tests OTE','Mauvaise branche et mauvais ancrage M1/LTF','Impulsion LTF depuis pivot confirmé, extrême sur toutes ses bougies et FVG actifs connus','Cas corrigés passent; définition graphique du pivot reste conventionnelle'),
 ('M4A/B','Range09:30–09:45 NY puis cassure/retest ou rejet vers borne opposée','Deux branches présentes, range absent avant09:45','test_opr_m15_unavailable_before_0945; Model.opening','Exécution M1, corps0,6, une tentative/session et fenêtre80 sont conventions, pas S9 vérifié intégralement','Conventions exposées; aucun ajustement de résultat','Range causal vérifié; fidélité partielle et séquences de marché non reconstruites'),
 ('M5A','Range5min→cassure→retest→confirmation; next quote','Chemin CSV→ordre14:38→fill open14:38 disponible14:39 dans scénario technique','final-checked/M5-retest; baseline/M5A-events.jsonl','Moteur pouvait réutiliser capital d’une sortie future intrabougie','Blocage si position déjà ouverte au début de la bougie','Régression corrigée; historique/rejeu identiques'),
 ('M5B','FVG3bougies, troisième clôture forte, prix ultérieur, cible2R prévue','Next open correct; force de troisième bougie absente du contrôle initial','baseline/m5-third-before.txt; final-checked/M5-fvg-gap','Une troisième bougie faible déclenchait quand même','Direction et corps0,6 à troisième bougie, même seuil déjà déclaré; ouverture réelle suivante','Faible bougie refusée; gap exécuté au prochain ask/bid, jamais clôture garantie'),
 ('M6A/B/C','Définitions numériques, continuation et retournement séparés','A/B quantifiés; C pouvait acheter en clôturant encore sous le niveau cassé','baseline/regression-before.txt; tests M6 retest et contexte','M6C confirmation erronée; retournement initialement absent','Clôture côté correct et base après CHoCH; context_mode distinct expérimental','Régression passe; fidélité visuelle complète non vérifiée'),
 ('E1–E5','Politiques distinctes, quantités réelles et frais','E2/E3 demandaient par erreur une cible structurelle; gap E4 pouvait ignorer le partiel','baseline/regression-before.txt; baseline/partial-gap-before.txt','Rejets injustifiés ou résultat brut incorrect en gap','Cible fixe calculée avant test de cible; partiel à ouverture connue avant solde','Moitié2R+moitiéBE=1R brut; gaps partiels pondérés correctement'),
 ('Commun','Pivots/zones/FVG causaux, sweeps bornés','Confirmations causales; sweep retardé perdu dès première clôture extérieure','tests disponibilité; baseline/regression-before.txt','Sweep à réintégration suivante absent','Pending sweep borné, sans réécrire la cassure de structure passée','Persistant non sweep; réintégration bornée nouvel événement'),
 ('Commun','Instrument réel et compte correctement identifiés','Pas d’API de données; import déclaratif; devise compte CAD ignorée','baseline/regression-before.txt; gold-status; live-current-attempt.txt','Étiquette seule ne prouve aucune source; USD/CAD non implémenté','provider_symbol et account_currency explicites, CAD et symboles ETF/futurs refusés','Contrôles locaux passent; flux OANDA effectif reste non vérifiable'),
 ('Direct','Redémarrage, doublon, gap, données périmées','Idempotence présente; latch HALTED oublié après restart','test_halt_latch_survives_restart_and_keeps_position','Reprise pouvait perdre l’arrêt opérationnel','Latch SQLite persistant; protections conservées, empreinte du flux chaînée','Rejeu/stream commun identique; aucun flux actuel reçu'),
 ('Recherche','Résultats par fenêtre, occasion et coûts cohérents','Ancien état final répété par fenêtre; stress ask pouvait casser OHLC; occasions absentes','stress_bar, opportunity_metrics, evaluate diff; tests comptables','Présentation temporelle et dénominateur incomplets','États par frontière, enveloppe OHLC, cohortes avec non-fill et censures, minimum échantillon avant verdict','Tests logiciels passent; génération positive de rapport marché encore non exercée')]

verdicts=[]
technical = {'M1':'Parcours H1/M5 et H4/M15 et contact sans CHoCH testés; géométrie discrétionnaire non certifiée', 'M2':'Sélection achat/vente, exclusion du futur et cible parent testées; pas de reconstruction brute M2 de marché', 'M3':'Tests de branche FVG et ancrages LTF; pas de reconstruction brute de marché', 'M4A':'Range causal testé; séquence de confirmation contrôlée dans code, sans cas brut de marché', 'M4B':'Range causal testé; rejet numérique présent, sans cas brut de marché', 'M5A':'Parcours CLI complet, quote ultérieure, reprise et régression intrabougie testés', 'M5B':'Parcours CLI complet avec gap et bougie faible refusée; arrivée réelle du flux non validée', 'M6A':'Conditions numériques et mode de contexte exécutables; fidélité et trajectoire brute complète non certifiées', 'M6B':'Conditions numériques exécutables; fidélité et trajectoire brute complète non certifiées', 'M6C':'Régression de retest corrigée; contextes séparés, branche expérimentale'}
for method in ['M1','M2','M3','M4A','M4B','M5A','M5B','M6A','M6B','M6C']:
    verdicts.append({'model':method,'fidelity':'partiel','evaluation':'données insuffisantes',
        'technical':technical[method],
        'reason':'Noyau public comparé aux ASR; géométries/confirmations numériques et filtres projet non certifiés par graphiques; aucune donnée de marché vérifiée.'})

tests=(OUT/'tests-final.txt').read_text();count=int(re.search(r'Ran (\d+) tests',tests).group(1))
evidence={'source_revision':revision(ROOT),'baseline_commit':'24e2258','version':'0.3.0','tests_passed':count,
    'test_log':'tests-final.txt','fidelity_verdicts':verdicts,
    'active_default_check':json.loads((OUT/'active-defaults-checked/verification.json').read_text()),
    'market_performance':{'status':'données insuffisantes','provider':None,'data_hash':None,'period':None,'metrics':None},
    'scope':{'reference':'OANDA:XAUUSD','canonical':'XAUUSD','api_symbol_convention':'XAU_USD','actual_provider_request':None,
             'account_currency':'USD uniquement; CAD refusé','source_integrity':'métadonnées déclarées et empreintes, aucune authentification de CSV fournisseur'},
    'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in video_files+list(OUT.glob('source-tv-*.json'))+list(OUT.glob('*passages.json'))},
    'parameters':json.loads((ROOT/'configs/primary.json').read_text()),
    'comparison_parameters':json.loads((ROOT/'configs/audit-comparisons.json').read_text()),
    'browser':'serve échoue PermissionError avant écoute; Chromium TargetClosedError; graphiques matplotlib exportés et examinés',
    'holdout':'Aucun jeu de marché final consulté. Les dates exemple ne constituent pas une réserve réelle. Figer une période intacte après obtention des données, avant mesure.',
    'synthetic_rule':'Uniquement fixtures et preuves logicielles, jamais une évaluation de rentabilité'}
(OUT/'verdicts.json').write_text(canonical(evidence))

lines=['# Audit indépendant du laboratoire XAU/USD — version0.3.0','',
       '## Conclusion','',
       '**Fidélité globale partielle pour toutes les méthodes ; performance de marché : données insuffisantes pour toutes.** Des noyaux publics sont retrouvés et plusieurs erreurs techniques ont été reproduites puis corrigées. Une fidélité partielle ne signifie ni perte ni gain de marché : aucune série réelle vérifiée n’a été testée. Les tests synthétiques ci-dessous valident le logiciel exclusivement.','',
       f"Code contrôlé : `{evidence['source_revision']['commit']}` ; hash `{evidence['source_revision']['code_hash']}`. Référence avant corrections : `24e2258`. {count} tests logiciels passent.",'',
       '## Référence et premier écart concret','',
       '`baseline/reference.json`, `baseline/active-configurations.json`, CSV bruts, manifestes, événements JSONL et journaux SQLite locaux conservent la référence avant correction. Les SQLite de tests sont locaux et exclus de Git ; leurs exports JSONL sont versionnés. Aucun journal prospectif de marché n’a été réécrit.','',
       'Le scénario M1 trace un ordre décidé07:40UTC puis exécuté sur retracement après décision. Le M5A trace une décision14:38UTC et une exécution à l’ouverture14:38, connue dans ce moteur à bougies à14:39. Les chiffres sont des dates de fixtures logicielles, pas des trades Gold observés. Les fixtures historiques existantes emploient pivots1/1 et désactivent les protections Gold ; M1H1 attend60min et le cas H4/M15 attend180min pour exercer les états. Ces valeurs de tests diffèrent des défauts actifs2/2, protections activées et attente30min. Elles sont archivées, pas choisies sur un résultat de marché.','',
       'Le premier défaut est conservé dans `baseline/M5-future-exit-reproducer-events.jsonl` : M5B sort avec le high de la minute14:40–14:41, puis M5A est exécuté rétroactivement à14:40. Cela libérait une position et du capital avant de connaître sa sortie. La réexécution CLI sur le même CSV conserve deux OPEN avant correction contre un seul après, dans causality-before-after.json; le deuxième est désormais refusé, sans modification des paramètres numériques. `occupied_at_open` empêche désormais cette nouvelle entrée. Une cible ou un partiel déjà franchi dès la première quote est en revanche traité avant les touches ultérieures ; un gap ne supprime plus le partiel E4.','',
       '## Instrument, unités et données','',
       'Les pages publiques relues indiquent OANDA:XAUUSD. La convention API OANDA est XAU_USD (BASE_QUOTE, documentation officielle archivée). Mais l’application n’a actuellement **aucun lecteur API de cours** : CSV/Parquet et fichier JSONL seulement. Il n’existe donc aucune requête fournisseur réelle à certifier. Le symbole, le fournisseur, le produit, la source, les unités et la devise sont des déclarations à l’import, protégées par empreintes ; les H4/D1 sont reconstruits avec ancrage UTC, sans alignement de session OANDA/TradingView authentifié ; un booléen verified ne prouve pas l’authenticité d’un fichier.','',
       'Les contrôles imposent XAU/USD en USD par once troy, quantités en contrats dont les onces sont explicites, valeur du point cohérente, bid/ask distincts, calendrier fournisseur sourcé et compte USD. CAD est bloqué, sans conversion fictive. GLD/GC/NQ ne passent pas sous provider_symbol. L’exemple de contrat reste non vérifié et ne désigne aucun compte OANDA. Les écarts avec un autre fournisseur ne sont pas mesurables sans deux séries réelles sur une même période.','',
       'Volume courant : absent faute de flux. La définition publique OANDA du volume de bougie est « number of prices created », pas un volume mondial de transactions. Le Volume Profile du code répartit uniformément le volume OHLC dans32bins : approximation, POC=bin maximal, VA70%, jamais un profil final futur. Aucun filtre de stratégie Volume Profile n’est actif. Les heures locales de S6 restent non authentifiées ; les sessions Gold IANA sont des conventions de contexte distinctes.','',
       '## Tableau des constats et corrections','',
       '| Modèle | Règle attendue | Comportement observé | Preuve | Écart | Correction | Résultat après correction |',
       '|---|---|---|---|---|---|---|']
for row in rows:lines.append('| '+' | '.join(x.replace('|','/') for x in row)+' |')
lines += ['', '## Verdicts séparés','', '| Méthode | Fidélité | Exactitude technique locale | Évaluation de marché |','|---|---|---|---|']
for v in verdicts:lines.append(f"| {v['model']} | {v['fidelity']} | {v['technical']} | {v['evaluation']} |")
lines += ['',
 'M1 conserve une structure à pivots fixes et une zone pivot de la bougie précédant la clôture de CHoCH : ce n’est pas une reproduction visuelle discrétionnaire complète. M2 sélectionne à l’activation du parent, sans redessiner ensuite. M3 fige la branche sur les FVG encore actifs de l’impulsion ancrée au dernier pivot opposé confirmé. M4 utilise une exécution M1 et des seuils de programmation qui ne sont pas tous authentifiés par S9. M5 respecte le range et le next quote, mais ajoute des filtres numériques et un seul ordre par session. M6 a désormais des modes continuation/reversal séparés dans la configuration d’audit ; leur contexte HTF est une hypothèse expérimentale, sans certification visuelle. Les seuils Gold obligatoires de primary/variants sont des ajouts du projet H11–H15, pas des règles OlinVest.','',
 '## Épreuves réellement réalisées','',
 '- Invariance par plusieurs préfixes, données futures supprimées et modifiées : événements, snapshots et objets connus comparés. Les variantes existantes sont aussi couvertes par la suite unitaire.','- Parité : même StreamingSession.ingest que live, avec une horloge virtuelle à clôture+1seconde clairement étiquetée REJEU EN FLUX. Ce n’est pas une connexion de marché actuelle. received_at contrôle la fraîcheur mais ne décale pas les available_at nominaux du moteur : la latence réelle et la première cotation accessible après arrivée restent non vérifiées. Réconciliation des événements et positions, redémarrage et doublons.','- Incidents : flux ancien, donnée future/corrigée, gap, redémarrage sous verrou, position conservée et protections continuées. Le latch SQLite persiste maintenant.','- Comptabilité : moitié2R/moitiéentrée=1R brut ; commissions de toutes jambes ; stop au prix d’entrée peut perdre net ; gaps et partiels à ouverture connue ; dimensionnement et marge.','- Visualisations : `final-checked/*/visual/decision.png` et `after.png`, plus les manifestes. Premier événement de chaque fixture indépendante de gain, perte, absence, non-fill et ambiguïté ; pas une sélection d’exemples de marché. Les zones ne sont tracées qu’après leur disponibilité.','- Application : commandes import-data, verify-engine, export-decision, gold-status, refus synthétique de history/preregister, tentative live normale et probe2secondes exécutées. Le serveur HTTP normal est bloqué par le sandbox à socket.socket(EPERM) ; Chromium n’a pas démarré. Le navigateur de cette version reste donc non vérifié.','',
 'La publication S12 est datée26novembre2024 et contient bien le post-scriptum sans confirmation/sans entrée. Date et texte connus ne suffisent pas : limites précises de zone, fuseau du graphique et série M1 correspondante n’ont pas été reconstruits. Le cas aucun-trade est volontairement technique. Les images des11vidéos n’ont pas été vérifiées ; les nombres ASR sensibles restent signalés dans le registre.','',
 '## Performance et protocole','',
 'Aucune métrique financière de marché publiée : occasions, trades, espérance, drawdown, frais, séries de pertes et sensibilité sont tous **non mesurés** sur XAU/USD réel. Les transactions des fixtures sont uniquement des preuves de comptabilité et de causalité. Les cas ambiguës portent des bornes nettes de scénarios d’ordre intrabougie ; dans la fixture dédiée, le stop prioritaire est retenu. Aucun impact statistique de ces ambiguïtés sur le Gold réel n’est connu.','',
 '`configs/audit-comparisons.json` préenregistre18modèles,54simulations au coût×1/×2/×3 dans budget120 : M1/direct même parent, M1/sweep, M2/parent, M5A/M5B/cassure simple, E4/sortieunique, M6 continuation/reversal. Les paires E4/sortieunique ont un filtre structurel commun strictement supérieur à2R pour éviter de confondre effet de sortie et éligibilité. Les occasions partagées sont identifiées, les non-fill et censures comptés. Les états de compte sont maintenant pris à la fin de chaque fenêtre, pas à la fin du test global. Le stress OHLC conserve une enveloppe ask cohérente et reste une approximation.','',
 'Aucun seuil des méthodes n’a été réglé sur un résultat de marché. Les corrections changent la version et exigent une nouvelle expérience prospective. Les données déclarées incomplètes par le fournisseur sont maintenant refusées même si leur date est passée; en absence de ce drapeau, le CSV est seulement attesté final par son exporteur. Les paramètres et spécifications sont copiés pour empêcher une mutation externe silencieuse après initialisation. Les anciennes dates de splits sont des exemples, pas un test final effectivement réservé. Après obtention du jeu réel, figer coûts, dates et configurations avant évaluation ; ne pas élire les paramètres avec le test final. Le bootstrap journalier est implémenté mais aucun walk-forward de marché ni intervalle d’incertitude de marché n’a été exécuté. La recherche actuelle est à paramètres fixes, sans entraînement ni optimisation automatique.','',
 '## Reproduction et étapes bloquantes','',
 'Voir `REPRODUCE.md` pour les cinq points d’entrée et `final-checked/commands.json` pour les21commandes exactes déjà exécutées avec leurs codes de sortie. Voir `rules-audited.json` pour sources, horodatages issus des segments, paramètres et tests. `tests-final.txt` est le journal de tests.','',
 'Étape manquante précise : fournir un export réel XAU/USD M1 bid/ask et ses métadonnées vérifiées (symbole fournisseur effectif, contrat, tick, compte, calendrier et provenance). L’import pourra alors être lancé, puis le préenregistrement avec un découpage réel et un test final intact. Pour le direct, un exporteur autorisé doit alimenter des M1 clôturées actuelles ; aucun fichier ni identifiant n’est présent ici. Aucune comparaison fournisseur, performance historique/OOS ou réception actuelle ne peut être certifiée avant cela. Aucun ordre réel, aucun processus permanent lancé.']
(OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')

matrix=['# Registre indépendant des règles auditées','',
        'Les horodatages sont pris dans start_ms des segments récupérés, jamais reconstruits de mémoire. Les transcriptions sont automatiques et les images restent non vérifiées.','']
for r in rules:
    matrix += [f"## {r['rule_id']} — {r['model']}",r['expected'],'',r['translation_status'],'',f"Code : `{r['code']}`",f"Paramètres actifs : {r['active_parameters']}",f"Tests : {', '.join(r['tests'])}"]
    for s in r['sources']:
        matrix += [f"- [{s['id']} {s.get('timestamp','texte public')}]({s['url']}) : {s.get('quote','passage non localisé')} ({s.get('status','documentation publique')})"]
    matrix += ['']
(OUT/'RULE_MATRIX.md').write_text('\n'.join(matrix).rstrip()+'\n')
print(canonical({'rules':len(rules),'tests':count,'models_with_verdict':len(verdicts),'market_performance_measured':False}))
