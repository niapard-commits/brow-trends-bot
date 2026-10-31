# Заявка Meta App Review для threads_keyword_search

Статус на 31.10.2026: токен із явним дозволом працює, пошук без помилок, дописів 0 (до схвалення видно лише власні дописи browtrendsdigest23).

## Опис використання
Brow Trends Digest is a small, private market-research tool used by one individual beauty professional (eyebrow and eyelash services) in Slovakia. It uses threads_keyword_search to search PUBLIC Threads posts for a fixed list of keywords related to brow lamination, brow shaping/tinting and lash lifts (in Ukrainian, Slovak and English). Once a week the tool collects the matching public posts (text, username, permalink, timestamp, media type) and prepares an aggregated digest of the topics and questions people discuss, with links to the original posts, so the operator can create original educational content on the topics clients ask about. The tool does not publish, reply, like, follow or message anyone, does not build profiles of individuals, does not use data for advertising or model training, and deletes raw results after 90 days. Privacy policy: https://niapard-commits.github.io/brow-trends-legal/

## Інструкція для рецензента
The tool runs as a scheduled GitHub Actions workflow in a private repository, so there is no public login. The screencast shows: (1) the app and the permission in the Meta dashboard, (2) the workflow run calling GET /keyword_search with the access token of the operator's test account, (3) the resulting data file containing public post text, username, permalink and timestamp, and (4) the weekly digest built from it. Test user: the Threads account browtrendsdigest23 (added as Threads Tester).

## Сценарій відео (1–2 хв, запис екрана)
1. Meta-застосунок → Use cases: видно threads_keyword_search.
2. GitHub → Actions → collect → Run workflow → успішний запуск.
3. data/digest-input.md: дописи з посиланнями та іменами користувачів.
4. Політика конфіденційності в браузері.

## Що лишилось
- Опублікувати тестовий допис від browtrendsdigest23 і запустити collect (щоб у відео були результати).
- Записати відео, у Meta: Use cases → Permissions → threads_keyword_search → Дії → «Додати в запит на перевірку», далі App Review.
- Вирішити, як тижневий дайджест потрапляє в артефакт для дружини.
