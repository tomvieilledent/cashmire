# Guide Cashmire — fonctionnement complet + 100 questions/réponses

> Basé sur le code réel du dépôt (branche `docs/58-qa-security-review`, après merge de `main`).

---

## 1. Vue d'ensemble en 2 minutes

**Cashmire** = application web de suivi de dépenses et de budgets personnels, en français. Slogan : « Le luxe discret pour votre budget au quotidien. »

| Couche | Techno |
|---|---|
| Frontend | SvelteKit (Svelte 5, runes), Vite, SPA (`ssr = false`), LayerChart (graphiques), lucide (icônes), Vitest |
| Backend | Django 5.1 + Django REST Framework 3.15, drf-spectacular (OpenAPI), django-cors-headers |
| Base de données | PostgreSQL 16 |
| Orchestration | Docker Compose (`db`, `api`, `frontend`) |
| Auth | Session Django (cookie `sessionid`) + CSRF (`csrftoken` / `X-CSRFToken`), pas de JWT |

**Flux type** : navigateur (Svelte, :5173) → `fetch` avec `credentials: "include"` → API Django (:8000, `/api/...`) → PostgreSQL (:5432).

**Entités** : `User` (email = identifiant) → `Category` (par utilisateur) → `Expense` (dépense) et `Budget` (budget par catégorie et période).

**Règle métier centrale** : un budget = montant + période + catégorie. Le serveur calcule `spent` (somme des dépenses de la catégorie dans la période, bornes incluses), `remaining`, `percentage` et `status` (`ok` / `warning` / `full` / `exceeded`).

**Arborescence utile**
- `backend/api/` : `models.py`, `serializers.py`, `views.py`, `urls.py`, `auth.py`, `signals.py`, `exceptions.py`, `services/budget_consumption.py`, `management/commands/seed_demo_data.py`, `tests/`
- `backend/cashmire/` : `settings.py`, `urls.py`
- `frontend/src/routes/` : `+layout.svelte`, `+page.svelte` (accueil), `login`, `register`, `expenses`, `budgets`, `privacy`, `health`
- `frontend/src/lib/` : `api.js`, `auth.svelte.js`, `money.js`, `dashboard.js`, `api/*.js`, `components/*`, `styles/*`
- `docs/` : `api-design.md`, `erd.md`, `mvp-scope.md`, `decisions/` (ADR), `git-workflow.md`, `team.md`, `agentic-log.md`
- `agentic/` + `.github/agents/` : workflow multi-agents IA

---

## 2. Les 100 questions / réponses

### A. Général et produit (1–10)

**1. C'est quoi Cashmire ?**
Une application web de suivi de dépenses et de budgets personnels : on enregistre ses dépenses par catégorie, on fixe des budgets par période, et on voit sa consommation avec des statuts et des graphiques.

**2. Qui est la cible ?**
Des particuliers qui veulent suivre simplement leurs dépenses, sans la complexité d'un outil comptable (voir `docs/mvp-scope.md`, « Utilisateurs cibles »).

**3. Quelles fonctionnalités le MVP contient-il ?**
Inscription/connexion/déconnexion par session, CRUD des dépenses, CRUD des budgets avec consommation calculée, catégories par défaut, tableau de bord avec 3 graphiques, page de confidentialité, accessibilité et Docker.

**4. Qui a fait quoi dans l'équipe ?**
Tom : produit, architecture, agentic, budgets backend, audit sécurité. Jason : backend (API, base, auth, dépenses). Clément : frontend, DevOps/Docker, accessibilité, démo (`docs/team.md`).

**5. Comment lance-t-on le projet ?**
`cp .env.example .env` puis `docker compose up --build`. Front : http://localhost:5173, API : http://localhost:8000/api/health/.

**6. Quels sont les services Docker ?**
`db` (postgres:16-alpine, volume `pgdata`, healthcheck), `api` (Django `runserver` sur 8000, dépend de `db` healthy), `frontend` (Vite dev sur 5173, dépend de `api`).

**7. Pourquoi le fichier `docker-compose.yml` s'appelle maintenant `compose.yaml` ?**
Il a été renommé sur `main` (nom canonique de Compose v2). Les commandes `docker compose ...` restent identiques.

**8. Qu'est-ce qu'un MVP et pourquoi c'est important ici ?**
Produit minimum viable : projet de 4 jours, donc périmètre volontairement réduit (`docs/mvp-scope.md` liste aussi ce qui est hors périmètre : pas de budgets récurrents, etc.).

**9. Comment l'équipe travaille-t-elle avec Git ?**
Branches `<type>/<issue>-<slug>`, commits Conventional Commits, PR vers `main` relue par un autre membre, pas de push direct sur `main` (`docs/git-workflow.md`).

**10. Qu'est-ce que le workflow « agentic » ?**
Trois agents IA spécialisés (Product & Architecture, Full-Stack Development, QA & Security), définis dans `.github/agents/*.md` et orchestrés par `agentic/orchestrator.py` avec le Claude Agent SDK. Chaque usage est consigné dans `docs/agentic-log.md` (objectif, ce qui a été délégué, vérification, accepté/rejeté, décision finale).

---

### B. Architecture et infrastructure (11–20)

**11. Pourquoi Django + DRF ?**
Django fournit ORM, migrations versionnées, auth, sessions, CSRF et admin. DRF ajoute les vues API, les serializers et la validation. Le README précise que ça évite un outil de migration séparé.

**12. Pourquoi SvelteKit ?**
Svelte 5 est léger et réactif (runes `$state`, `$derived`), SvelteKit fournit le routage par fichiers. Ici on l'utilise en SPA (`export const ssr = false` dans `+layout.js`).

**13. Pourquoi `ssr = false` ?**
L'authentification repose sur un cookie de session lu côté navigateur, et l'état « connecté » est résolu au montage via `/api/auth/me/`. Pas de rendu serveur, donc pas de problème d'hydratation ni de cookies côté serveur Node.

**14. Comment le front connaît-il l'URL de l'API ?**
Via `VITE_API_URL` (défaut `http://localhost:8000`), lue une fois dans `api.js` (`API_BASE_URL`). C'est l'URL que le navigateur appelle directement, donc jamais `http://api:8000`.

**15. Comment le backend choisit-il l'hôte Postgres ?**
`POSTGRES_HOST` est laissé vide : `settings.py` détecte le service `db` dans Docker, sinon `localhost` (API lancée hors conteneur).

**16. À quoi sert le volume `/app/node_modules` dans le service frontend ?**
Volume anonyme qui empêche le bind-mount `./frontend:/app` d'écraser les `node_modules` installés dans l'image. Conséquence : après ajout d'une dépendance, il faut rebuilder avec `--renew-anon-volumes` (c'est ce qui causait l'erreur `layerchart` introuvable).

**17. Que fait `DJANGO_DEBUG` ?**
Active le mode debug. Il conditionne aussi `/api/schema/` et `/api/docs/` (404 si `false`) et la commande `seed_demo_data`.

**18. Que se passe-t-il si la base est vide au lancement ?**
Il faut `docker compose exec api python manage.py migrate`, sinon `relation "api_user" does not exist` et l'inscription renvoie 500 (c'est arrivé après recréation du volume).

**19. Comment fonctionne CORS ici ?**
`corsheaders` autorise `DJANGO_CORS_ALLOWED_ORIGINS` (défaut `http://localhost:5173`) avec `CORS_ALLOW_CREDENTIALS = True`, nécessaire pour envoyer les cookies en cross-origin.

**20. Pourquoi `CSRF_TRUSTED_ORIGINS` en plus de CORS ?**
CORS et CSRF sont indépendants : `CsrfViewMiddleware` vérifie aussi l'en-tête `Origin`. Sans cette liste on obtient « CSRF Failed: Origin checking failed » même avec le bon token.

---

### C. Base de données et modèles (21–35)

**21. Quels modèles existent ?**
`User`, `Category`, `Expense`, `Budget` (`backend/api/models.py`).

**22. Pourquoi un `User` personnalisé ?**
Pour avoir un `email` unique en base utilisé comme identifiant (`USERNAME_FIELD = "email"`) et des timestamps `created_at` / `updated_at`. Il hérite d'`AbstractUser` (mot de passe haché, `is_active`, etc.).

**23. Le `username` est-il encore demandé ?**
Il reste requis et unique en base, mais le formulaire d'inscription n'envoie que email + mot de passe : `generate_unique_username` le dérive de la partie locale de l'email, dédoublonné en cas de collision.

**24. Comment sont stockés les montants ?**
`DecimalField(max_digits=10, decimal_places=2)`, jamais de float. Côté API, ils sont sérialisés en chaînes JSON.

**25. Pourquoi des chaînes JSON pour l'argent ?**
Éviter les erreurs d'arrondi des flottants IEEE 754. Le front applique la même règle (voir `money.js`).

**26. Quelles contraintes protègent `Expense` ?**
`CheckConstraint(amount > 0)`. FK `user` en `CASCADE`, FK `category` en `PROTECT`. Tri par défaut `-date, -id`.

**27. Quelles contraintes protègent `Budget` ?**
`amount > 0`, `period_end >= period_start`, `alert_threshold` NULL ou entre 0 et 100, et `UNIQUE(user, category, period_start, period_end)`. Deux index : `(user)` et `(user, period_start, period_end)`.

**28. Que signifie `on_delete=PROTECT` sur la catégorie ?**
On ne peut pas supprimer une catégorie utilisée par des dépenses ou des budgets : Django lève `ProtectedError`. Cela évite des dépenses orphelines.

**29. Que signifie `CASCADE` sur `user` ?**
Supprimer un utilisateur supprime ses catégories, dépenses et budgets.

**30. Les catégories sont-elles partagées entre utilisateurs ?**
Non : elles sont par utilisateur (décision `category-ownership.md`) avec `UNIQUE(user, name)`. Raison : personnalisation, confidentialité, contrôle d'accès simple.

**31. D'où viennent les catégories d'un nouvel utilisateur ?**
D'un signal `post_save` sur `User` (`signals.py`) qui crée les 12 catégories de `DEFAULT_CATEGORIES` via `bulk_create` (Alimentation, Transport, Logement, Loisirs, Santé, Vêtements, Éducation, Divertissement, Services, Épargne, Investissements, Autres).

**32. Pourquoi `not raw` dans le signal ?**
`raw=True` correspond au chargement de fixtures (`loaddata`) : on ne doit pas créer de catégories automatiquement à ce moment-là.

**33. Quel est le rôle de `dispatch_uid` ?**
Empêche que le récepteur soit enregistré deux fois (évite les doublons de catégories).

**34. Quelle valeur par défaut pour `alert_threshold` ?**
80,00 (nullable). Si `NULL`, le service applique 80 %.

**35. Comment sont gérées les migrations ?**
Migrations Django versionnées dans `backend/api/migrations` (`0001` user, `0002` category, `0003` expense, `0004` budget…). Appliquées avec `python manage.py migrate`.

---

### D. Authentification et sécurité (36–50)

**36. Comment fonctionne l'authentification ?**
Session Django : `login(request, user)` crée une session en base et pose le cookie `sessionid`. Le client ne stocke aucun token (ADR 0003).

**37. Pourquoi pas JWT ?**
Avec JWT dans `localStorage`, un XSS peut voler le token. Le cookie de session est `HttpOnly` donc illisible par JS, la déconnexion invalide vraiment la session côté serveur, et Django le gère déjà.

**38. Qu'est-ce que le CSRF et comment l'évite-t-on ?**
Une attaque où un autre site déclenche une requête avec vos cookies. Django pose un cookie `csrftoken` (lisible par JS, non `HttpOnly`) ; `api.js` le lit et l'envoie dans `X-CSRFToken` pour POST/PUT/PATCH/DELETE.

**39. Quand DRF applique-t-il le CSRF ?**
`SessionAuthentication` ne l'applique que pour les requêtes authentifiées. Register/login n'ont pas de session utilisateur à la requête ; logout, dépenses, budgets sont protégés.

**40. Pourquoi `SessionCookieAuthentication` existe-t-elle ?**
Elle surcharge `authenticate_header` pour renvoyer `"Session"` : sans en-tête `WWW-Authenticate`, DRF transforme les 401 en 403. Avec elle, un anonyme reçoit bien **401** (issue #143).

**41. Différence entre 401 et 403 dans l'API ?**
401 = non authentifié (session absente/invalide). 403 = authentifié mais requête refusée (par exemple échec CSRF).

**42. Comment fonctionne le login ?**
`POST /api/auth/login/` (email + password) → `authenticate()`. Si échec : 401 `{"detail": "Invalid email or password."}`. Sinon `login()` et 200 avec le user.

**43. Comment évite-t-on de révéler si un email existe ?**
Même 401 et même message pour « email inconnu » et « mauvais mot de passe ». Django exécute aussi le hachage sur une valeur factice pour limiter l'attaque par temps de réponse.

**44. Y a-t-il une protection contre le brute-force ?**
Oui, minimale : `ScopedRateThrottle` scope `login` à **5/min par IP** (ADR 0004). Limites : une IP partagée se bloque mutuellement, et ça ne protège pas un compte attaqué depuis plusieurs IP. L'inscription n'est pas limitée.

**45. Comment les mots de passe sont-ils stockés ?**
Hachés par `set_password` (PBKDF2 par défaut en Django), jamais en clair. Le champ est `write_only`.

**46. Quelles règles de mot de passe ?**
Les 4 validateurs Django : similarité avec les attributs utilisateur, longueur minimale (8), mot de passe courant, entièrement numérique. Le front impose aussi `minlength=8`.

**47. Comment se déconnecte-t-on ?**
`POST /api/auth/logout/` (authentifié + CSRF). `logout()` vide la session côté serveur et renvoie 204.

**48. Comment le front sait-il si on est connecté ?**
`auth.svelte.js` : au montage de la navbar, `refreshCurrentUser()` appelle `GET /api/auth/me/`. 200 → `authenticated`, 401 → `anonymous` (cas normal, pas une erreur).

**49. Comment empêche-t-on un utilisateur de lire les données d'un autre ?**
Toutes les requêtes filtrent par `user=request.user`. Une dépense ou un budget d'autrui renvoie 404 (pas 403) pour ne pas révéler son existence. Une catégorie étrangère donne aussi 404.

**50. Que renvoie l'API en cas d'erreur serveur ?**
`sanitized_exception_handler` renvoie `{"error": "INTERNAL_SERVER_ERROR", "message": "An internal server error occurred."}` et logge la trace côté serveur : pas de fuite de stack trace.

---

### E. API : endpoints et validation (51–65)

**51. Liste des endpoints ?**
`GET /api/health/`, `POST /api/auth/register/`, `POST /api/auth/login/`, `GET /api/auth/me/`, `POST /api/auth/logout/`, `GET /api/categories/`, `GET|POST /api/expenses/`, `PATCH|PUT|DELETE /api/expenses/<id>/`, `GET|POST /api/budgets/`, `PATCH|DELETE /api/budgets/<id>/`, et en dev `/api/schema/`, `/api/docs/`.

**52. Que fait l'inscription ?**
`POST /api/auth/register/` valide, crée l'utilisateur (+ ses catégories via signal), puis fait `login()` : l'utilisateur est connecté immédiatement.

**53. Comment filtrer les dépenses ?**
Query params `category_id`, `date_from`, `date_to`. Validation : `date_from <= date_to`, sinon 400. Réponse : `{"expenses": [...]}`.

**54. Quelles validations pour créer une dépense ?**
`category_id` ≥ 1 et appartenant à l'utilisateur (sinon 404), `amount` chaîne décimale ≥ 0,01 avec max 10 chiffres/2 décimales, `date` valide, `description` optionnelle.

**55. Pourquoi `DecimalStringField` ?**
Il refuse un nombre JSON (`12.5`) et exige une chaîne (`"12.50"`), pour garantir qu'aucun flottant n'entre dans le système.

**56. Différence PUT / PATCH sur une dépense ?**
Même serializer ; PATCH est « partial » (champs optionnels), PUT exige les champs obligatoires.

**57. Que renvoie un DELETE de dépense ?**
204 sans corps. Si la dépense n'existe pas ou appartient à autrui : 404 « Dépense non trouvée ».

**58. Quelles validations pour créer un budget ?**
`amount > 0`, `period_end >= period_start`, `alert_threshold` entre 0 et 100, catégorie de l'utilisateur (404 sinon).

**59. Que renvoie la création d'un doublon de budget ?**
409 Conflict « Budget déjà existant pour cette période et catégorie ». Double défense : vérification applicative + contrainte unique en base avec `transaction.atomic()` et capture d'`IntegrityError` (race condition).

**60. Peut-on filtrer les budgets ?**
Oui : par période et par `category_id` (catégorie étrangère → simplement filtrée, aucun résultat). Réponse : `{"budgets": [...]}` avec `spent`, `remaining`, `percentage`, `status`.

**61. Pourquoi la liste de budgets est-elle calculée en un seul passage ?**
`calculate_consumption_batch` fait **une seule requête SQL** pour toutes les dépenses concernées, puis agrège en Python : pas de problème N+1.

**62. Quelle est la différence entre `calculate_consumption` et `..._batch` ?**
La première traite un budget (agrégation SQL `Sum`), la seconde plusieurs budgets avec une requête unique.

**63. Les bornes de période sont-elles incluses ?**
Oui : une dépense à `period_start` ou `period_end` compte (`date__gte` / `date__lte`).

**64. Comment documenter/tester l'API ?**
drf-spectacular génère le schéma OpenAPI (`/api/schema/`) et Swagger UI (`/api/docs/`), accessibles uniquement si `DJANGO_DEBUG=true` (ADR 0005). Les tests sont dans `backend/api/tests/` (≈215 tests au dernier audit).

**65. Pourquoi masquer Swagger en production ?**
Éviter d'exposer gratuitement la cartographie de l'API. Cela ne remplace pas l'authentification des routes (issue #144).

---

### F. Logique des budgets (66–75)

**66. Comment calcule-t-on `spent` ?**
Somme des `Expense.amount` de l'utilisateur, pour la catégorie du budget, avec `date` dans `[period_start, period_end]`.

**67. Comment calcule-t-on le pourcentage ?**
`spent / amount × 100`, quantifié à 2 décimales, non plafonné à 100 (pour détecter le dépassement).

**68. Quels sont les statuts ?**
`ok` (< seuil), `warning` (seuil ≤ % < 100), `full` (= 100 %), `exceeded` (> 100 %) (`budget-thresholds.md`).

**69. Pourquoi distinguer `full` et `exceeded` ?**
Dépenser exactement le budget n'est pas un dépassement. On évite d'afficher « Dépassé » à quelqu'un qui a pile consommé son budget.

**70. À partir de quand « Proche de la limite » ?**
Dès que `spent >= amount × seuil / 100` (borne inférieure incluse). Avec seuil 80 % sur 500 € : à partir de 400 €.

**71. Que se passe-t-il si `alert_threshold = 100` ?**
Le statut `warning` disparaît : on passe de `ok` directement à `full`.

**72. Pourquoi le statut est-il calculé sans arrondi ?**
Comparer des `Decimal` bruts évite qu'un 79,996 % arrondi à 80,00 déclenche à tort un warning.

**73. Pourquoi le front ne recalcule-t-il pas le statut ?**
Une seule source de vérité (serveur) pour éviter des divergences aux bornes. Le front affiche `status` tel quel.

**74. Pourquoi ma dépense n'augmentait pas le pourcentage de mon budget (cas réel) ?**
La dépense (09/10/2026) était hors période du budget (01–30/11/2026). Seules les dépenses dans la période et la catégorie comptent.

**75. Pourquoi voit-on « Sous contrôle » et « Proche de la limite » en même temps dans le graphique ?**
Parce que plusieurs budgets de même catégorie existent sur des périodes différentes (sept, oct, nov), avec des statuts différents. La légende liste les statuts présents, pas un budget unique.

---

### G. Frontend : architecture (76–90)

**76. Comment est structuré le routage ?**
SvelteKit par fichiers : `/` (accueil), `/login`, `/register`, `/expenses`, `/expenses/new`, `/expenses/[id]/edit`, `/budgets`, `/budgets/new`, `/budgets/[id]/edit`, `/privacy`, `/health`.

**77. Qu'est-ce que `+layout.svelte` ?**
Le shell commun : importe les styles (tokens, fonts, base, `layerchart/core.css`), affiche `Navbar`, la page (`{@render children()}`) puis `Footer`.

**78. Comment le front appelle-t-il l'API ?**
Via `apiFetch` (`lib/api.js`) : base URL, en-têtes JSON, encodage JSON du corps, header CSRF automatique sur les méthodes non sûres, et lève une `ApiError` pour tout non-2xx. Les appels de session passent `credentials: "include"`.

**79. Que vaut `ApiError.status === 0` ?**
Échec réseau/DNS/CORS (le `fetch` lui-même a échoué). C'est ce qui affiche « Impossible de joindre Cashmire » dans les formulaires.

**80. Pourquoi `apiFetch` ne convertit-il jamais les nombres ?**
Règle binding : les montants restent des chaînes. Pas de `Number()`/`parseFloat()`.

**81. À quoi sert `money.js` ?**
Arithmétique décimale exacte sur des chaînes avec `BigInt` : `compareDecimal`, `addDecimal`, `subtractDecimal`, `sumDecimal`, `percentOf`, `formatAmount`. Aucun `Number`, `Math`, `toFixed`, `Intl.NumberFormat` (vérifié par un test qui scanne le code source).

**82. Pourquoi `percentOf` tronque au lieu d'arrondir ?**
Pour ne jamais afficher 100,0 % alors que le badge dit « Proche de la limite ». La troncature ne peut que sous-estimer.

**83. Pourquoi ne pas comparer les chaînes avec `<` ?**
Comparaison lexicographique : `"9.0" >= "80"` est `true`. On utilise `compareDecimal`.

**84. Quel est le rôle de `toPlotNumber` ?**
Seule exception autorisée : convertir en `Number` uniquement pour les échelles/pixels de LayerChart/D3, jamais pour comparer ou calculer.

**85. Comment fonctionne `auth.svelte.js` ?**
Un singleton `$state` (`user`, `status`) exposé via des getters pour rester réactif. `setCurrentUser` après login/register évite un appel `/me` supplémentaire.

**86. Que fait la Navbar ?**
Liens Accueil, Dépenses, Budgets, Confidentialité, Connexion/Inscription ou Déconnexion. Les liens protégés sont toujours visibles mais interceptés pour un anonyme. Menu mobile (icônes `Menu`/`X`).

**87. Que contient le tableau de bord ?**
`DashboardCharts` charge catégories, dépenses et budgets **une seule fois** en parallèle (`Promise.all`) et alimente 3 graphiques : budget vs dépensé par catégorie, répartition des dépenses du mois (camembert), tendance sur 30 jours.

**88. Pourquoi un seul fetch centralisé pour les graphiques ?**
Les 3 graphiques partagent les mêmes données ; trois fetchs séparés tripleraient les appels non paginés.

**89. Que fait `dashboard.js` ?**
Fonctions pures d'agrégation : `budgetVsSpentRows`, `spendingByCategory`, `dailyTotals` (zéro-rempli pour chaque jour), `currentMonthWindow`, `last30DaysWindow`. Faciles à tester sans framework.

**90. Pourquoi les dates sont-elles construites avec les champs locaux ?**
`toISOString()` lit l'UTC et peut donner le mauvais jour près de minuit ; on utilise `getFullYear/getMonth/getDate`.

---

### H. Frontend : UI, accessibilité, tests (91–100)

**91. Comment l'accessibilité est-elle gérée ?**
La couleur n'est jamais le seul signal : chaque statut a une icône + un libellé. Champs avec labels, `aria-valuenow` sur les barres de progression, `aria-labelledby` sur les sections.

**92. Quels libellés de statut sont affichés ?**
« Sous contrôle », « Proche de la limite », « Budget atteint », « Budget dépassé », « Inconnu » en repli.

**93. Comment sont stylés les composants ?**
Styles scoped par composant + variables CSS globales (`tokens.css`), polices (`fonts.css`), base (`base.css`), `charts.css`. Pas de framework CSS ni de thème switcher (ADR 0001).

**94. Quels composants réutilisables existent ?**
`Button`, `TextField`, `FormError`, `Navbar`, `Footer`, `ExpensesList`, `BudgetsList`, `BudgetForm` et les 3 graphiques. `ExpensesList`/`BudgetsList` sont réutilisés sur l'accueil avec `limit={3}`.

**95. Comment gère-t-on les états chargement/erreur ?**
Machine à états `loading | ready | error` dans les composants qui fetchent, avec message d'erreur et bouton « réessayer ».

**96. Comment le front distingue-t-il 401 et 403 dans les formulaires ?**
401 → « session requise » ; 403 → échec de vérification de la requête/CSRF (issue #143). Les deux ont des tests de régression.

**97. Comment teste-t-on le front ?**
Vitest + jsdom + Testing Library Svelte (`npm test`, ≈134 tests au dernier audit). `resolve.conditions: ["browser"]` quand `VITEST` est défini, pour éviter le build serveur de Svelte.

**98. Comment teste-t-on le backend ?**
`docker compose run --rm api python manage.py test api` : tests par domaine (`test_login`, `test_expenses`, `test_budgets`, `test_logout`, `test_current_user`, `test_errors`, `test_api_docs_access`…).

**99. Comment génère-t-on des données de démo ?**
`python manage.py seed_demo_data` (refuse de tourner si `DEBUG` est faux) : compte `demo@cashmire.example`, catégories, dépenses du mois et budgets ; relançable sans doublons.

**100. Quelles limites connues peut-on avouer en soutenance ?**
Rate-limit login par IP seulement, pas de limite sur l'inscription ; listes non paginées ; pas de CRUD de catégories (seulement les 12 par défaut) ; email non vérifié ; pas de HTTPS/cookies `Secure` configurés en dev ; findings de l'audit #58 (ex. contraste des cartes budget, énumération d'emails à l'inscription, login CSRF) à trier dans #59.

---

## 3. Pièges à connaître avant d'être interrogé

- **Ne jamais dire « JWT »** : c'est une session cookie.
- **Argent = chaînes + Decimal**, jamais de float (back et front).
- **404 plutôt que 403** pour les ressources d'autrui.
- **Statut calculé côté serveur uniquement.**
- **L'inscription connecte directement** l'utilisateur.
- Si une dépense « ne compte pas » dans un budget : vérifier **période** et **catégorie**.


