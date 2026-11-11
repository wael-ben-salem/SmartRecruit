# SmartRecruit — guide détaillé des fichiers et des choix

Ce document sert de support de validation et de soutenance. Il décrit le rôle des fichiers présents dans le dépôt et explique les principaux choix de conception. Pour comprendre le fonctionnement général, les commandes d'installation et les limites, voir aussi [projet.md](./projet.md) et [README.md](./README.md).

## 1. Présentation en quelques phrases

SmartRecruit est un prototype académique d'aide au rapprochement entre une offre d'emploi et plusieurs CV. Il lit les documents, transforme l'offre en critères, cherche dans chaque CV des passages qui peuvent servir de preuves, vérifie les citations, puis présente une comparaison au recruteur.

Le système est une aide à la lecture : il ne décide pas qui doit être recruté. Un résultat « non documenté » signifie que le CV ne contient pas de preuve retrouvée ; cela ne prouve pas que la personne ne possède pas la compétence.

## 2. Parcours d'une analyse

1. Le dashboard envoie l'offre et les CV à l'API FastAPI.
2. L'API crée un identifiant d'analyse (*run*) et conserve les fichiers nécessaires au traitement.
3. Le workflow n8n orchestre les étapes : lecture des documents, analyse de l'offre, préparation des profils et traitement des candidats.
4. Les pages PDF lisibles sont extraites avec PyMuPDF. Les pages scannées ou difficiles à lire peuvent passer par un modèle vision.
5. Le texte des CV est anonymisé avant les agents texte, puis découpé en passages et indexé dans Qdrant.
6. Le Matching Agent recherche des passages par critère et propose un statut avec des citations.
7. L'Audit Agent vérifie les citations et leur pertinence. Le calcul du score reste déterministe et réalisé en Python.
8. Le dashboard montre les résultats, les preuves, l'audit et permet au recruteur d'enregistrer sa décision.

## 3. Choix de conception à expliquer

| Choix | Pourquoi | Point de vigilance |
|---|---|---|
| n8n pour l'orchestration et une API Python séparée | Le workflow est visible et rejouable ; les traitements métier restent testables en code. | L'API permet aussi un mode direct sans n8n pour le développement. |
| Un traitement par exigences et par candidat | Chaque conclusion peut être reliée à un critère précis et à des passages du CV. | La qualité dépend de la lecture PDF et de la récupération de bons passages. |
| RAG avec Qdrant et embeddings bge-m3 | Recherche ciblée dans les CV, compatible avec plusieurs langues et avec des citations paginées. | La recherche dense n'est pas parfaite ; l'évaluation compare aussi le découpage et un baseline lexical. |
| Lecture PDF adaptative | Le texte est extrait localement quand il est exploitable ; la vision est réservée aux pages difficiles ou scannées. | Une image de CV envoyée au fournisseur vision peut encore contenir des données identifiantes. |
| Agents spécialisés et prompts versionnés | Chaque agent a un rôle et une sortie attendue distincts ; les versions sont conservées et comparables. | Les modèles peuvent halluciner ou interpréter incorrectement une preuve. |
| Audit en deux niveaux | Le code vérifie la présence de la citation ; le modèle évalue si elle appuie réellement le statut. | Un audit réduit le risque, sans garantir l'absence d'erreur. |
| Score calculé en Python | Le même statut et les mêmes pondérations donnent un résultat reproductible ; le LLM ne choisit pas le score final. | Le score mesure les preuves écrites dans le CV, pas la valeur d'une personne. |
| Anonymisation et contrôle humain | Réduire les informations personnelles visibles par les agents texte et laisser la décision au recruteur. | L'anonymisation est heuristique et n'efface pas les données visibles dans une image envoyée au modèle vision. |
| Tests et évaluations séparés | Les tests hors ligne vérifient les règles déterministes ; les scripts évaluent séparément retrieval, prompts, anonymisation et audit. | Les jeux d'évaluation sont petits et certains labels sont synthétiques ou générés par mots-clés. |

### Quelques résultats à présenter avec leurs réserves

- La récupération réelle de passages est évaluée sur 10 CV et 67 requêtes. La configuration par sections avec bge-m3 donne R@5 = 0,970 ; les labels sont des *silver labels* basés sur des motifs de mots-clés, pas encore une annotation indépendante complète.
- TOP_K est fixé à 5 pour réduire les preuves pertinentes manquées ; cela augmente la quantité de contexte et réduit la précision par rapport à k=3.
- L'évaluation de l'audit compare les prompts v2 et v3 sur 28 cas préparés. Le résultat est encourageant, mais ne constitue pas une garantie en production.
- L'évaluation d'anonymisation rapporte 0 fuite sur 29 identifiants plantés et 0 suppression erronée sur 18 textes utiles ; le jeu a été conçu par l'équipe et le résultat peut être optimiste.
- Les tests unitaires hors ligne valident notamment le score, les citations, l'anonymisation, le découpage et le routage PDF, sans clé API.

Les détails, métriques, commandes de reproduction et limites sont dans [eval/RETRIEVAL_EVAL.md](./eval/RETRIEVAL_EVAL.md), [eval/audit_results.md](./eval/audit_results.md), [eval/anonymization_results.md](./eval/anonymization_results.md), [docs/PRIVACY_AND_FAIRNESS.md](./docs/PRIVACY_AND_FAIRNESS.md) et [projet.md](./projet.md).

## 4. Fichiers à la racine

| Fichier | Rôle |
|---|---|
| `.env.example` | Modèle des variables d'environnement à copier vers `.env`. La clé API doit rester vide dans le modèle et être fournie localement, jamais commitée. |
| `.gitattributes` | Règles Git communes, notamment pour le traitement cohérent des fins de ligne. |
| `.gitignore` | Exclut du suivi Git les fichiers locaux, secrets, dépendances et résultats temporaires prévus par le projet. |
| `README.md` | Présentation rapide, architecture, démarrage, démonstration et accès aux évaluations. |
| `projet.md` | Dossier en français : fonctionnalités, architecture, installation Windows, configuration, validation et questions possibles de soutenance. |
| `detail.md` | Présent document : rôle des fichiers et justification des principaux choix. |
| `PROMPT_LIBRARY.md` | Catalogue des prompts, versions actives, évolutions, échecs visés et comparaisons des agents. |
| `docker-compose.yml` | Lance l'API, n8n, Qdrant et Ollama, configure leurs URLs et monte les données, prompts et fichiers utiles. |

## 5. API Python

### Démarrage, configuration et orchestration

| Fichier | Rôle |
|---|---|
| `api/Dockerfile` | Construit l'image du service API et définit son environnement d'exécution. |
| `api/requirements.txt` | Déclare les bibliothèques Python : FastAPI, PyMuPDF, client LLM compatible OpenAI, Qdrant, HTTP, rapports et outils PDF/image. |
| `api/smartrecruit/__init__.py` | Marque `smartrecruit` comme package Python. |
| `api/smartrecruit/config.py` | Centralise les réglages issus de l'environnement : LLM, vision, embeddings, Qdrant, prompts, découpage et rétention. |
| `api/smartrecruit/main.py` | Crée l'application FastAPI, expose les routes utilisées par le dashboard et n8n, reçoit les fichiers et sert les résultats. |
| `api/smartrecruit/dashboard_api.py` | Regroupe les routes destinées au dashboard : état, résultats, historique, décisions et suppression des analyses. |
| `api/smartrecruit/pipeline.py` | Enchaîne les étapes métier en Python pour exécuter ou déboguer le pipeline sans dépendre de l'orchestration n8n. |
| `api/smartrecruit/steps.py` | Fournit les opérations réutilisées par le workflow : lecture, anonymisation, agents, indexation, matching, audit et rapport. |
| `api/smartrecruit/static/index.html` | Page HTML statique de secours/de démonstration servie par l'API lorsque le dashboard React n'est pas utilisé. |

### Documents, modèles et traitement métier

| Fichier | Rôle |
|---|---|
| `api/smartrecruit/pdf_reader.py` | Lit les PDF page par page, choisit extraction texte ou vision, et conserve des informations de lecture et de pagination. |
| `api/smartrecruit/anonymizer.py` | Applique les règles et heuristiques de suppression d'identifiants personnels avant les agents texte. |
| `api/smartrecruit/chunking.py` | Découpe le texte des CV en passages adaptés à la recherche, en conservant autant que possible les sections et le contexte. |
| `api/smartrecruit/embeddings.py` | Génère les vecteurs de texte via le fournisseur configuré, Ollama par défaut. |
| `api/smartrecruit/vectorstore.py` | Crée et interroge les collections Qdrant, indexe les passages et filtre les recherches par analyse et candidat. |
| `api/smartrecruit/llm.py` | Centralise les appels aux modèles compatibles OpenAI, le format JSON et les modèles de repli configurés. |
| `api/smartrecruit/prompts.py` | Charge les fichiers de prompts versionnés et prépare les messages transmis aux modèles. |
| `api/smartrecruit/skills.py` | Normalise les noms de compétences avec les synonymes locaux et, selon la configuration, les données ESCO. |
| `api/smartrecruit/jobfetch.py` | Récupère le contenu d'une offre publique par URL et en extrait le texte exploitable. |
| `api/smartrecruit/scoring.py` | Calcule les scores à partir des statuts et pondérations définis, et tient compte de la qualité de lecture. |
| `api/smartrecruit/report.py` | Produit le rapport HTML comparatif avec critères, scores, citations et résultats d'audit. |
| `api/smartrecruit/store.py` | Enregistre et relit les données JSON/JSONL d'une analyse, journalise des événements, supprime et purge les anciennes données. |

### Agents

| Fichier | Rôle |
|---|---|
| `api/smartrecruit/agents/__init__.py` | Marque le répertoire des agents comme package Python. |
| `api/smartrecruit/agents/job_agent.py` | Analyse l'offre et produit les exigences structurées, conditions et critères écartés. |
| `api/smartrecruit/agents/cv_agent.py` | Transforme le CV anonymisé en profil structuré avec compétences et éléments de preuve. |
| `api/smartrecruit/agents/matching_agent.py` | Compare chaque exigence aux passages retrouvés et propose un statut accompagné de citations. |
| `api/smartrecruit/agents/audit_agent.py` | Vérifie la présence des citations et demande une vérification sémantique de leur adéquation au statut. |

### Tests API

| Fichier | Rôle |
|---|---|
| `api/tests/test_offline.py` | Tests sans appels aux modèles : règles de score, anonymisation, citations, stratégies de découpage et lecture/routage PDF. |

## 6. Dashboard React

| Fichier | Rôle |
|---|---|
| `dashboard/README.md` | Notes de démarrage et de développement du dashboard. |
| `dashboard/.gitignore` | Exclut les dépendances, sorties de build et fichiers locaux propres au dashboard. |
| `dashboard/package.json` | Déclare les commandes npm et les bibliothèques React, icônes et graphiques utilisées par l'interface. |
| `dashboard/package-lock.json` | Verrouille les versions résolues des dépendances npm pour des installations reproductibles. |
| `dashboard/eslint.config.js` | Configure ESLint pour vérifier le code JavaScript/React. |
| `dashboard/index.html` | Document HTML de départ chargé par Vite. |
| `dashboard/vite.config.js` | Configure Vite et le serveur de développement, notamment le lien vers l'API. |
| `dashboard/src/main.jsx` | Point d'entrée React : initialise et monte l'application dans la page. |
| `dashboard/src/App.jsx` | Assemble les vues, gère l'analyse sélectionnée, le suivi d'état et l'historique. |
| `dashboard/src/api.js` | Centralise les requêtes HTTP du frontend vers les routes de l'API. |
| `dashboard/src/index.css` | Définit les styles globaux, la mise en page, les couleurs et les états des composants. |
| `dashboard/src/components/NewRun.jsx` | Formulaire de création d'une analyse : choix de l'offre et ajout des CV. |
| `dashboard/src/components/Progress.jsx` | Affiche l'avancement des étapes et les erreurs pendant le traitement. |
| `dashboard/src/components/Results.jsx` | Présente les candidats, scores, critères, preuves, audit, rapport, suppression et décision humaine ; contient aussi les éléments graphiques de résultats. |
| `dashboard/src/components/History.jsx` | Affiche les analyses passées et permet de rouvrir une analyse. |

Les changements visibles dans l'état actuel du dashboard enrichissent notamment l'affichage des étapes et des résultats. `lucide-react` fournit des icônes ; `recharts` fournit des composants de visualisation. `react-is` est une dépendance de compatibilité utilisée par l'écosystème des graphiques.

## 7. Workflow, prompts et documents

| Fichier | Rôle |
|---|---|
| `n8n/smartrecruit.json` | Export du workflow n8n qui orchestre les appels à l'API et les étapes du traitement. |
| `docs/PRIVACY_AND_FAIRNESS.md` | Décrit le parcours des données, la rétention, l'anonymisation, l'équité, le contrôle humain et les limites réglementaires. |
| `docs/REPORT_DRAFT.md` | Brouillon de rapport de projet, distinct du rapport HTML produit pour une analyse. |
| `docs/SmartRecruit_Agents_Brief.docx` | Document de cadrage présentant le projet et ses agents. |
| `prompts/vision_reader/v1.md` | Instructions au modèle vision pour retranscrire une page difficile à extraire. |
| `prompts/cv_agent/v1.md` | Première version du prompt d'extraction de profil CV. |
| `prompts/cv_agent/v2.md` | Version structurée du prompt CV, avec règles de preuve et format de sortie resserré. |
| `prompts/job_agent/v1.md` | Première version du prompt d'analyse de l'offre. |
| `prompts/job_agent/v2.md` | Version affinée pour mieux classer et atomiser les exigences. |
| `prompts/job_agent/v3.md` | Version active par défaut ; distingue notamment exigences, conditions et critères à écarter. |
| `prompts/matching_agent/v1.md` | Première version du prompt de comparaison exigences-CV. |
| `prompts/matching_agent/v2.md` | Version active par défaut, avec statuts définis, citations verbatim et retour éventuel de l'audit. |
| `prompts/audit_agent/v1.md` | Première version du prompt de vérification sémantique des conclusions. |
| `prompts/audit_agent/v2.md` | Version affinée qui distingue plusieurs types de verdict et corrections possibles. |
| `prompts/audit_agent/v3.md` | Version active par défaut, évaluée dans les cas de test décrits dans les documents d'évaluation. |

Les versions sont conservées séparément pour pouvoir expliquer et comparer l'évolution des consignes plutôt que de remplacer silencieusement le prompt précédent.

## 8. Données de démonstration et d'essai

Ces fichiers servent à la démonstration, à la préparation des cas et à l'évaluation. Ils ne constituent pas tous des données de production. Vérifier les licences et les conditions d'utilisation avant de redistribuer des CV ou données externes.

| Fichier | Rôle |
|---|---|
| `data/skills_synonyms.json` | Table locale de synonymes et variantes d'écriture des compétences. |
| `data/deletions.jsonl` | Journal des suppressions d'analyses, conçu pour conserver une trace minimale. |
| `data/demo/README.md` | Explique le jeu de démonstration et ses fichiers. |
| `data/demo/job_it_support_specialist.txt` | Offre d'emploi utilisée avec les CV de démonstration. |
| `data/demo/cv_24038620.pdf` | CV de démonstration sous forme PDF. |
| `data/demo/cv_24038620_scanned.pdf` | Variante scannée du CV ci-dessus pour éprouver le chemin de lecture vision. |
| `data/demo/cv_39718499.pdf` | Autre CV de démonstration. |
| `data/demo/cv_46260230.pdf` | Autre CV de démonstration. |
| `data/jobs/offers/it_manager.txt` | Offre utilisée dans les essais sur les offres d'emploi. |
| `data/jobs/offers/it_support_specialist.txt` | Offre IT support utilisée dans la préparation des évaluations réelles. |
| `data/jobs/offers/systems_administrator.txt` | Offre utilisée dans les essais sur les offres d'emploi. |
| `data/jobs/offers/sources.json` | Métadonnées de provenance des offres enregistrées. |
| `data/samples/job_offer_data_engineer.txt` | Offre fictive de référence pour le pipeline et les tests de démonstration. |
| `data/samples/job_offer_data_engineer.pdf` | Version PDF de cette offre fictive. |
| `data/samples/cv_A_single_column.pdf` | CV fictif de test à une colonne. |
| `data/samples/cv_B_two_columns.pdf` | CV fictif de test à deux colonnes. |
| `data/samples/cv_C_scanned.pdf` | CV fictif scanné, utilisé pour tester le chemin vision. |
| `data/samples/ground_truth/cv_A_single_column.txt` | Texte de référence associé au CV fictif A. |
| `data/samples/ground_truth/cv_B_two_columns.txt` | Texte de référence associé au CV fictif B. |
| `data/samples/ground_truth/cv_C_scanned.txt` | Texte de référence associé au CV fictif C. |
| `data/consistency/wording_original.pdf` | Document de test pour comparer des formulations. |
| `data/consistency/wording_synonyms.pdf` | Variante avec synonymes pour les essais de cohérence. |
| `data/consistency/missing_page2.pdf` | Cas de test où une page manque, pour étudier la robustesse de lecture. |

Les répertoires `data/uploads/`, `data/runs/` et éventuellement `data/esco/` sont des emplacements de travail : les premiers contiennent des fichiers d'analyse, le dernier peut recevoir les données ESCO téléchargées pour l'indexation. Ils ne sont pas décrits comme des sources immuables du projet.

## 9. Évaluations, annotations et scripts

### Fichiers de résultats et jeux de test

| Fichier | Rôle |
|---|---|
| `eval/RETRIEVAL_EVAL.md` | Méthode, résultats et limites de l'évaluation de recherche des passages. |
| `eval/anonymization_results.md` | Résultats de l'évaluation des identifiants supprimés et du texte utile préservé. |
| `eval/audit_results.md` | Comparaison des résultats d'audit sur un jeu de cas préparés. |
| `eval/audit_results_run2.md` | Résultats d'un second passage d'évaluation de l'audit. |
| `eval/audit_cases.json` | Cas et étiquettes utilisés pour évaluer l'audit. |
| `eval/audit_results.json` | Résultats structurés de l'évaluation de l'audit. |
| `eval/queries.json` | Requêtes de test de recherche, notamment pour le corpus synthétique. |
| `eval/queries_real.json` | Requêtes de recherche associées au jeu de CV réel. |
| `eval/results_real.json` | Résultats détaillés de retrieval sur le jeu réel. |
| `eval/results_real.md` | Présentation lisible de résultats du jeu réel et des rangs obtenus. |
| `eval/results_synthetic.json` | Résultats structurés de retrieval sur le jeu synthétique. |
| `eval/results_synthetic.md` | Présentation lisible des résultats synthétiques. |
| `eval/demo_run_response.json` | Exemple de réponse structurée d'une analyse de démonstration. |
| `eval/run_real.log` | Journal d'exécution d'une évaluation réelle. |
| `eval/annotation/retrieval_labels_real.csv` | Feuille d'annotation humaine prévue pour contrôler la pertinence des passages retrouvés. |
| `eval/annotation/review_20261028-160545-a88e88.csv` | Feuille d'examen manuel liée à une exécution identifiée par date et identifiant. |

### Scripts de préparation et d'évaluation

| Fichier | Rôle |
|---|---|
| `scripts/make_samples.py` | Génère les CV fictifs et PDFs de test avec des mises en page différentes. |
| `scripts/download_resumes.py` | Télécharge le jeu de CV externe prévu pour certaines évaluations. |
| `scripts/prepare_real_data.py` | Prépare les données réelles et leurs variantes d'essai, notamment des copies scannées. |
| `scripts/ingest_esco.py` | Importe des données ESCO dans la base de vecteurs pour enrichir la normalisation/recherche de compétences. |
| `scripts/eval_retrieval.py` | Compare les stratégies de découpage et de retrieval sur les requêtes de test. |
| `scripts/eval_anonymization.py` | Mesure les identifiants qui restent et les textes utiles supprimés par erreur sur les cas conçus. |
| `scripts/eval_consistency.py` | Compare la cohérence de résultats entre des versions/formulations de documents. |
| `scripts/eval_audit.py` | Évalue et compare les prompts d'audit sur des cas étiquetés. |
| `scripts/compare_prompts.py` | Compare des versions de prompts pour les agents concernés et exporte les résultats. |
| `scripts/export_review.py` | Exporte les résultats d'une analyse sous forme de feuille destinée à une revue humaine. |
| `scripts/score_review.py` | Calcule les mesures de concordance à partir des annotations de revue. |

## 10. Présentation du projet

| Fichier | Rôle |
|---|---|
| `presentation/project/deck.json` | Manifeste du diaporama et de ses paramètres de génération. |
| `presentation/project/slides/cover.html` | Diapositive de couverture. |
| `presentation/project/slides/context.html` | Contexte et problème traité. |
| `presentation/project/slides/scope.html` | Périmètre du prototype. |
| `presentation/project/slides/plan.html` | Plan de la présentation. |
| `presentation/project/slides/architecture.html` | Architecture générale des composants. |
| `presentation/project/slides/stack.html` | Technologies du projet. |
| `presentation/project/slides/pipeline.html` | Étapes du pipeline d'analyse. |
| `presentation/project/slides/agents.html` | Rôles des agents. |
| `presentation/project/slides/prompts.html` | Travail de conception et de versionnement des prompts. |
| `presentation/project/slides/multimodal.html` | Lecture multimodale des documents. |
| `presentation/project/slides/rag-corpus.html` | Corpus et index utilisés par le RAG. |
| `presentation/project/slides/rag-eval.html` | Évaluation de la recherche des passages. |
| `presentation/project/slides/demo.html` | Démonstration du fonctionnement. |
| `presentation/project/slides/next.html` | Limites et suites envisagées. |
| `presentation/project/slides/team.html` | Présentation de l'équipe. |
| `presentation/project/slides/question.html` | Diapositive de questions. |

## 11. Questions possibles pendant la validation

**Pourquoi utiliser plusieurs agents ?** Les tâches sont séparées : comprendre l'offre, structurer le CV, comparer les preuves puis contrôler les conclusions. Chaque étape a une responsabilité plus facile à expliquer et à évaluer.

**Pourquoi ne pas envoyer tout le CV au modèle de matching ?** La recherche RAG fournit des passages ciblés par exigence, avec leur contexte et leurs métadonnées. Cela facilite les citations et évite de transmettre systématiquement tout le document à chaque comparaison.

**Pourquoi le score est-il calculé en code ?** Pour que la pondération soit explicite et reproductible, au lieu de laisser le modèle inventer une note. Le modèle propose les statuts ; le code applique les règles.

**Que veut dire « missing » ?** Aucune preuve suffisante n'a été retrouvée dans le contenu lu du CV. Ce statut ne permet pas de conclure que la personne ne possède pas la compétence.

**À quoi sert l'Audit Agent ?** À détecter une citation absente ou une conclusion exagérée. Une citation peut exister sans démontrer le critère ; le contrôle de présence et le contrôle de sens sont donc deux vérifications différentes.

**Le système est-il juste ou conforme pour un recrutement réel ?** Le projet met en place des garde-fous et documente certaines mesures, mais ne revendique ni absence de biais ni conformité complète. Il faudrait des validations indépendantes, une analyse juridique et de confidentialité, un suivi continu et une supervision adaptée avant tout usage réel.

## 12. Sécurité des clés

`.env` contient les paramètres locaux et ne doit pas être partagé ni commité. `.env.example` ne doit contenir qu'un exemple sans secret. Si une vraie clé a été ajoutée à un fichier ou partagée, il faut la révoquer et en créer une nouvelle auprès du fournisseur, même après avoir nettoyé le fichier.
