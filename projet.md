# SmartRecruit — dossier du projet

## 1. Résumé

SmartRecruit est un prototype académique d’aide à la comparaison de CV avec une offre d’emploi. Le recruteur fournit une offre et plusieurs CV PDF. Le système extrait et structure les informations, recherche des passages de preuve dans chaque CV, vérifie les citations et produit une comparaison explicable.

**Le système recommande ; le recruteur décide.** Le score mesure la présence de preuves dans le CV, pas la valeur d’une personne. « Non documenté » ne signifie pas que le candidat ne possède pas la compétence.

Le projet est construit comme une chaîne de traitement multi-agent, orchestrée principalement par n8n, avec une API Python qui réalise le traitement des documents, l’accès aux modèles et le calcul déterministe du score.

## 2. Fonctionnalités présentes

- Import d’une offre par URL publique, texte collé ou fichier PDF/TXT.
- Import d’un ou plusieurs CV PDF.
- Lecture PDF par page : extraction texte pour les pages simples, modèle vision pour les scans et mises en page à colonnes.
- Anonymisation heuristique des informations personnelles avant les agents texte.
- Extraction structurée du profil du candidat et des exigences de l’offre.
- Recherche RAG des passages pertinents du CV, avec métadonnées de page et de section.
- Analyse de correspondance par exigence, avec statut, justification et citations.
- Audit des citations et des conclusions, avec une seule nouvelle tentative de matching si nécessaire.
- Calcul de score pondéré en code et production d’un rapport comparatif.
- Suivi d’exécution, historique, suppression et enregistrement de la décision du recruteur dans le dashboard.

## 3. Architecture et déroulement

```text
Dashboard React
    │ offre + CV PDF
    ▼
API FastAPI ── création d'un run et conservation des documents
    │
    ├── n8n (par défaut) : orchestre les étapes et leur parallélisme
    │      ├── branche offre : lecture → Job Analysis Agent
    │      └── branche CV, pour chaque candidat :
    │             lecture PDF → anonymisation → CV Agent → indexation Qdrant
    │
    └── après préparation : Matching Agent → Audit Agent → rapport
                                  │
                                  └── recherche bge-m3 dans Qdrant
```

Le dashboard permet également de décocher l’option n8n : l’API appelle alors le même pipeline directement en Python. Ce mode est utile pour le développement et le débogage. Le workflow n8n exporté est [n8n/smartrecruit.json](./n8n/smartrecruit.json).

### Étapes détaillées

1. **Création du run** — l’API copie les fichiers dans `data/uploads/<run_id>/`, attribue des identifiants tels que `candidate_A`, puis conserve les métadonnées du run.
2. **Lecture de l’offre et des CV** — PyMuPDF extrait les pages. Les pages simples gardent leur texte localement. Les scans ou pages à colonnes sont rendus en images et envoyés au modèle vision configuré.
3. **Anonymisation des CV** — règles et heuristiques retirent notamment noms détectés, coordonnées et certains attributs sensibles. La sortie anonymisée est utilisée pour les agents texte et l’indexation.
4. **Job Analysis Agent** — transforme l’offre en exigences structurées, identifie les critères éliminés et sépare les conditions de travail. Les types et poids sont fixés en code : *must-have* = 2, *nice-to-have* = 1.
5. **CV Agent** — transforme le texte anonymisé en profil structuré (expériences, compétences, formation, etc.) et normalise les libellés de compétences.
6. **Indexation RAG** — découpe le CV en segments, puis stocke leurs embeddings et métadonnées dans Qdrant. Le filtre de recherche associe obligatoirement `run_id` et `candidate_id`.
7. **Matching Agent** — pour chaque exigence, récupère jusqu’à `TOP_K` passages et propose `met`, `partial` ou `missing`, avec citations tirées du CV.
8. **Audit Agent** — vérifie d’abord par code que les citations existent (avec tolérance aux différences d’OCR), puis demande au LLM si elles justifient le statut. Si des affirmations sont rejetées, le matching est relancé au plus une fois. Les affirmations toujours non étayées passent en `unverified`.
9. **Score et rapport** — le calcul n’est pas confié au LLM : `met` vaut 1, `partial` 0,5, et `missing`/`unverified` 0. Le rapport classe les dossiers et présente les preuves, l’audit et la qualité de lecture.

## 4. Technologies et raisons des choix

| Domaine | Choix dans le projet | Rôle / justification |
|---|---|---|
| Orchestration | n8n, workflow versionné dans `n8n/` | Étapes visuelles, observables et rejouables ; branche offre et traitement des CV en parallèle. |
| API et logique métier | Python 3.12, FastAPI, Uvicorn | Routes HTTP utilisées par n8n et le dashboard ; fonctions métier testables indépendamment. |
| Interface | React 19 et Vite 6 | Dashboard pour lancer une analyse, suivre la progression, consulter les résultats et l’historique. |
| Lecture PDF | PyMuPDF | Extraction du texte et rendu des pages en image pour la voie multimodale. |
| LLM texte et vision | API compatible OpenAI (valeurs par défaut définies dans `api/smartrecruit/config.py`, modifiables par variables d’environnement) | Sorties JSON des agents ; modèle distinct possible pour la vision et modèles de repli configurables. |
| Embeddings | Ollama local avec `bge-m3` par défaut | Embeddings multilingues FR/EN, calculés localement ; le fournisseur peut aussi être configuré en OpenAI-compatible. |
| Base vectorielle | Qdrant | Stockage/recherche des segments de CV et de la base optionnelle de compétences ESCO. |
| Données de run | Fichiers JSON/JSONL sous `data/runs/` | Conservation des résultats intermédiaires et journal d’audit, ce qui facilite inspection et rejeu. |
| Rapports | HTML produit par Python | Tableau des exigences, statuts, citations, contrôles et résumé par candidat. |

Les prompts sont conservés par agent et version dans [prompts/](./prompts/). Les versions actives par défaut sont définies dans `config.py` et peuvent être remplacées par les variables d’environnement `PROMPT_*`.

## 5. Organisation du dépôt

| Dossier/fichier | Contenu |
|---|---|
| `api/smartrecruit/` | Application, configuration, lecteurs PDF, anonymisation, agents, retrieval, scoring, stockage et rapports. |
| `api/smartrecruit/agents/` | Agents CV, analyse d’offre, matching et audit. |
| `api/tests/` | Tests hors ligne des fonctions déterministes, du routage PDF, des citations et du score. |
| `dashboard/` | Interface React/Vite et configuration de développement. |
| `n8n/` | Export du workflow d’orchestration. |
| `prompts/` et `PROMPT_LIBRARY.md` | Prompts versionnés et historique/notes de comparaison. |
| `data/samples/` | Jeu de démonstration fictif et vérités terrain. |
| `data/demo/` | Exemple de démonstration constitué d’une offre et de CV de démonstration. Ne pas utiliser ces fichiers comme preuve de performance générale. |
| `data/skills_synonyms.json` | Normalisation locale de synonymes et abréviations de compétences. |
| `scripts/` | Ingestion ESCO, préparation de données et scripts d’évaluation. |
| `eval/` | Requêtes, annotations, résultats et rapports d’évaluation. |
| `docs/PRIVACY_AND_FAIRNESS.md` | Données traitées, rétention, limites de confidentialité et supervision humaine. |
| `docker-compose.yml` | Services API, n8n, Qdrant et Ollama. |

## 6. Lancer le projet sous Windows

### Prérequis

- Docker Desktop démarré, avec Docker Compose.
- Node.js/npm pour construire le dashboard.
- Une clé d’API pour le LLM configuré (ex. Gemini), sauf si le fournisseur choisi ne l’exige pas.
- Accès réseau pour télécharger les images Docker, le modèle Ollama et, selon l’offre, appeler le fournisseur LLM.

### Première installation avec Docker (parcours recommandé)

Ouvrir PowerShell dans le dossier du dépôt :

```powershell
# Seulement si .env n'existe pas déjà : ne pas écraser une configuration locale existante.
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# Ouvrir .env dans un éditeur et définir LLM_API_KEY avec une clé valide.
# Construire le frontend React
npm --prefix dashboard ci
npm --prefix dashboard run build

# Construire et démarrer API, n8n, Qdrant et Ollama
docker compose up -d --build

# Télécharger les embeddings utilisés par défaut
docker compose exec ollama ollama pull bge-m3
```

Importer et activer le workflow la première fois. n8n utilise SQLite : le dépôt recommande de l’arrêter avant l’import :

```powershell
docker compose stop n8n
docker compose run --rm --no-deps n8n import:workflow --input=/workflows/smartrecruit.json
docker compose run --rm --no-deps n8n update:workflow --id=SmartRecruitMain --active=true
docker compose up -d n8n
```

La variable `MSYS_NO_PATHCONV=1` mentionnée dans le README est uniquement nécessaire si ces commandes sont exécutées depuis Git Bash/MSYS ; elle ne l’est pas dans PowerShell.

Vérifier que les services tournent :

```powershell
docker compose ps
Invoke-RestMethod http://localhost:8000/health
```

Puis ouvrir :

- Dashboard : [http://localhost:8000](http://localhost:8000)
- Interface n8n : [http://localhost:5678](http://localhost:5678) (créer le compte local lors de la première visite)
- Qdrant : `http://localhost:6333`

Dans le dashboard, choisir une offre (lien public, texte ou fichier), ajouter un ou plusieurs CV PDF et cliquer **Analyse**. Les pages scannées/multicolonnes nécessitent un modèle vision accessible. L’offre de démo et les CV sont dans `data/demo/`.

### Développement sans Docker

Le README fournit également un mode Python local pour tests et CLI. Il nécessite les services configurés (Qdrant/Ollama si l’on exécute tout le pipeline) et un environnement virtuel :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r api\requirements.txt
.\.venv\Scripts\python.exe -m pip install pytest

Push-Location api
..\.venv\Scripts\python.exe -m pytest tests -q
Pop-Location
```

Pour développer le dashboard séparément, garder l’API sur le port 8000 puis exécuter :

```powershell
npm --prefix dashboard run dev
```

Vite sert alors l’interface sur `http://localhost:5173` et transmet `/api` et `/runs` à l’API locale.

Le pipeline direct (sans n8n) peut aussi être lancé en ligne de commande depuis `api/` avec des chemins adaptés :

```powershell
Push-Location api
..\.venv\Scripts\python.exe -m smartrecruit.pipeline ..\data\samples\job_offer_data_engineer.txt ..\data\samples\cv_A_single_column.pdf ..\data\samples\cv_B_two_columns.pdf ..\data\samples\cv_C_scanned.pdf
Pop-Location
```

Les fichiers d’exemple sont fictifs ; un run complet a besoin d’un LLM et des services configurés. Pour un parcours sans LLM, exécuter uniquement les tests hors ligne.

### Arrêter les services

```powershell
docker compose down
```

Les volumes nommés n8n, Qdrant et Ollama sont conservés. Ne pas ajouter `-v` sauf si l’objectif explicite est d’effacer également ces données persistantes.

## 7. Configuration importante

Les valeurs sont lues par `api/smartrecruit/config.py` depuis l’environnement et `.env`. Ne jamais enregistrer une clé réelle dans Git, dans ce document ou dans un rapport.

| Variable | Fonction |
|---|---|
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Point d’accès, authentification et modèle texte. |
| `VISION_MODEL` | Modèle multimodal pour les pages PDF envoyées en image ; par défaut reprend le modèle texte. |
| `LLM_FALLBACK_MODELS` | Modèles utilisés si le quota journalier du modèle courant est épuisé. |
| `EMBED_PROVIDER`, `EMBED_MODEL`, `OLLAMA_URL` | Fournisseur, nom de modèle et URL pour les embeddings. |
| `QDRANT_URL` | URL Qdrant ; `:memory:` est utilisé pour certains tests/évaluations. |
| `CHUNK_STRATEGY`, `TOP_K` | Découpage des CV et nombre de passages récupérés par exigence. |
| `MIN_CHARS_PER_PAGE` | Seuil de caractères utilisé par le routeur PDF avant de privilégier la vision. |
| `PROMPT_CV_AGENT`, `PROMPT_JOB_AGENT`, `PROMPT_MATCHING_AGENT`, `PROMPT_AUDIT_AGENT`, `PROMPT_VISION_READER` | Version des prompts chargés. |
| `RETENTION_DAYS` | Durée de conservation locale des runs ; valeur par défaut 30 jours, 0 désactive la purge automatique. |

Un chargement ESCO est optionnel. Sans ESCO, le système utilise la table de synonymes. Avec ESCO, télécharger les données depuis le site officiel dans `data/esco/`, puis lancer `scripts/ingest_esco.py` dans le conteneur API selon les instructions du README.

## 8. Validation et éléments à défendre

### Tests techniques existants

`api/tests/test_offline.py` contient des tests sans appel au LLM ni embeddings pour :

- le choix extraction texte/vision sur PDF à une colonne, à deux colonnes et scanné ;
- l’anonymisation et la conservation des dates d’emploi ;
- les stratégies de découpage et leurs limites de taille ;
- le contrôle de citations exactes, approximatives (OCR) et inventées ;
- la normalisation des synonymes dans les requêtes ;
- le comportement du score, des exigences *must-have* et de la qualité de lecture.

Commande attendue depuis le dépôt :

```powershell
Push-Location api
python -m pytest tests -q
Pop-Location
```

Les scripts de `scripts/` valident séparément l’anonymisation, la retrieval, la cohérence scan/texte, les prompts et l’audit. Certaines évaluations nécessitent Ollama ou un quota LLM et peuvent être coûteuses ; les commandes et résultats sont décrits dans `README.md` et `eval/`.

### Résultats à présenter avec leurs réserves

- **Retrieval réel** : `eval/RETRIEVAL_EVAL.md` rapporte, pour *section + bge-m3*, R@1 = 0,642, R@3 = 0,881, R@5 = 0,970 et MRR = 0,768 sur 67 requêtes concernant 10 CV IT. Les étiquettes sont des *silver labels* basées sur des motifs de mots-clés, pas encore une annotation humaine indépendante.
- **Choix de `TOP_K=5`** : meilleure récupération (R@5 = 0,970 au lieu de 0,881 à k=3), au prix de plus de texte et d’une précision plus basse dans le contexte transmis. La décision privilégie la réduction des preuves manquées et reste à réévaluer.
- **Audit** : `eval/audit_results.md` rapporte pour l’audit v3 un taux de détection de 0,95, zéro fausse alerte dans ce jeu et 0,929 de verdict exact sur 28 cas. C’est un petit jeu de cas préparés, pas une garantie de performance en production.
- **Anonymisation** : les cas conçus dans `scripts/eval_anonymization.py` donnent 0 fuite sur 29 identifiants plantés et 0 suppression erronée sur 18 textes utiles. Le jeu est construit par l’équipe et les corrections ont été faites dessus ; le résultat est donc optimiste.
- **Tests de score** : les tests contrôlent des propriétés précises (par exemple un *must-have* pèse plus qu’un *nice-to-have*, une affirmation `unverified` vaut zéro).

### Questions de soutenance possibles

1. **Pourquoi n8n et une API séparée ?** n8n rend l’orchestration observable et rejouable ; l’API garde la logique métier testable, les accès aux modèles et les calculs.
2. **Pourquoi RAG pour les CV ?** Récupérer quelques passages ciblés par exigence conserve le contexte et donne des citations paginées, plutôt que d’envoyer systématiquement tout le CV au matching.
3. **Pourquoi l’audit est-il à deux niveaux ?** Une vérification code peut établir que la citation figure dans le CV ; elle ne peut pas décider à elle seule si cette citation prouve le niveau demandé. Un vérificateur LLM examine ce lien sémantique, avec une reprise limitée.
4. **Que signifie le score ?** Une moyenne pondérée des statuts documentés ; ce n’est ni une probabilité d’embauche ni une mesure de la valeur du candidat.
5. **Pourquoi garder une décision humaine ?** Les CV peuvent être mal lus, les preuves peuvent manquer et les modèles peuvent se tromper ; le système expose les éléments pour qu’un recruteur vérifie et décide.
6. **Quelles sont les limites principales ?** Petit corpus, annotations retrieval partiellement automatiques, anonymisation heuristique, variabilité des modèles, dépendance aux quotas, erreurs OCR/vision et validation indépendante encore nécessaire.

### Plan de validation à réaliser avant une démonstration

- Exécuter les tests backend dans un environnement isolé (venv ou Docker) et le lint/build du dashboard après installation de `dashboard/package-lock.json`.
- Vérifier `/health`, le démarrage de tous les conteneurs et une exécution réelle sur les CV fictifs.
- Comparer chaque citation de sortie au PDF d’origine, notamment pour les pages lues par vision.
- Faire annoter indépendamment un échantillon de résultats retrieval et de statuts par deux personnes ; rapporter les désaccords, pas seulement la moyenne.
- Mesurer la répétabilité des prompts en relançant l’audit avec `--repeats`, ainsi que les erreurs d’extraction sur plusieurs formats/langues.
- Pour toute utilisation avec des CV réels, vérifier la base légale, les conditions de rétention et le fournisseur de modèle. Le chemin vision transmet une image contenant potentiellement le nom/la photo **avant** anonymisation ; ne pas le présenter comme anonymisé de bout en bout.

## 9. Confidentialité, équité et sécurité des données

Les fichiers et sorties de run sont stockés localement sous `data/uploads/` et `data/runs/`. Les embeddings sont conservés dans le volume local Qdrant. La purge par défaut intervient à 30 jours ; la suppression depuis le dashboard supprime le run, les uploads et les vecteurs associés.

**Limite importante :** les pages scannées ou multicolonnes sont envoyées au fournisseur LLM sous forme d’image avant l’anonymisation. Les textes anonymisés sont également envoyés aux agents LLM. Les noms de fichiers originaux sont conservés pour l’interface recruteur. Ne pas utiliser de CV personnels sans vérifier les règles applicables et le contrat du fournisseur ; voir [docs/PRIVACY_AND_FAIRNESS.md](./docs/PRIVACY_AND_FAIRNESS.md).

L’anonymisation n’est pas garantie : détecteur de nom heuristique, contenu dans photos/logos et noms inhabituels non couverts. Les critères sensibles et conditions de travail sont exclus du score par la logique d’analyse de l’offre, mais cela ne démontre pas à lui seul l’absence de biais. Le projet est un prototype académique et ne revendique pas la conformité réglementaire ni une aptitude à prendre des décisions de recrutement autonomes.

## 10. Notes de démarrage et diagnostic rapide

- **API indisponible** : `docker compose ps`, `docker compose logs api`, puis vérifier `/health`.
- **n8n ne traite pas la demande** : confirmer que le workflow a été importé et activé ; consulter les exécutions dans l’interface n8n.
- **Erreur de clé/modèle** : contrôler les noms de variables dans `.env` sans publier leur valeur, et vérifier quota, modèle et `LLM_BASE_URL`.
- **Erreur d’embedding** : confirmer `docker compose exec ollama ollama list` et que `bge-m3` est présent ; vérifier que le conteneur API atteint `http://ollama:11434`.
- **Résultat de lecture incomplet** : examiner l’indicateur de qualité de lecture et les pages qui ont été routées vers vision ; vérifier les citations directement sur le PDF.
- **Ressources conservées** : `docker compose down` garde les volumes ; c’est intentionnel. La suppression des volumes est une opération distincte et efface les données persistantes des services.
