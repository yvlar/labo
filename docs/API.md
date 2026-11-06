# Clés API et connexions

Aucune clé API n’est nécessaire pour lancer le laboratoire, importer CSV/Parquet, rejouer des données, exécuter les tests ou calculer les backtests. Aucun modèle d’IA n’est appelé pendant les décisions de trading : aucune clé OpenAI, Gemini ou autre fournisseur d’IA n’est utilisée. Aucune clé TradingView ou OlinVest n’est requise.

## Données XAU/USD

Une clé de données peut être nécessaire selon le fournisseur choisi pour alimenter l’application automatiquement. Le besoin porte sur des données XAU/USD M1 bid/ask et, idéalement, historique et courant compatibles avec le même instrument précisément décrit. Une clé seule ne branche pas le laboratoire : un exporteur/adaptateur fournisseur doit alimenter le CSV ou le flux JSONL attendu. L’adaptateur courant du laboratoire lit ce fichier ; aucun SDK fournisseur n’est encore configuré.

L’accès doit être en lecture seule pour les données. Aucun droit de passer des ordres ou de retirer des fonds n’est nécessaire. Les clés restent dans l’environnement sécurisé de l’exporteur ou un mécanisme de secrets existant, jamais dans les métadonnées JSON, Git, journaux ou rapports. Le projet ne définit actuellement aucun nom de variable d’API obligatoire.

## Calendrier USD

Optionnel : les événements planifiés peuvent être renseignés dans la configuration préenregistrée avec leur source, horaire et disponibilité. Une API de calendrier nécessiterait éventuellement une seconde clé selon le fournisseur, mais aucune intégration n’est installée et aucune clé n’est exigée pour le calendrier manuel. Le filtre est vide et désactivé par défaut.

## Courtage

Aucune clé de courtage pour exécuter des ordres n’est utilisée. Seul le simulateur interne est autorisé. Les endpoints et comptes externes d’exécution restent bloqués. Une éventuelle source de cotations issue d’un courtier ne doit transmettre que ses données via un exporteur distinct et autorisé.
