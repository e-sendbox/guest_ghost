# Guest Ghost

Приложение-игрушка: подбирает жильё для приведений. В базе — справочник домов (замки, подвалы, чердаки) и заявки от приведений с именами и предпочтениями. Поиск — семантический: косинусное сходство векторов с персональным порогом (тревожность приведения).

## Стек

- **Frontend**: NiceGUI (Python UI)
- **Backend**: FastAPI, SQLite + sqlite-vec
- **LLM**: deepseek-v4-flash (Ollama Cloud)
- **Embedding**: jina-embeddings-v5-omni-nano (Jina, облако) / paraphrase-multilingual (Ollama, локально — запасной)

## Установка

### 1. Требования

- Python 3.10
- Ключи AI-провайдеров:
  - `OLLAMA_API_KEY` — https://ollama.com/settings/keys (LLM)
  - `JINA_API_KEY` — https://jina.ai/api-dashboard/key-manager (embedding)

### 2. Клонировать и установить зависимости

```bash
git clone <repo-url> guest_ghost
cd guest_ghost
pip install -r requirements.txt
```

### 3. Задать ключи

```bash
export OLLAMA_API_KEY="ХХХ"
export JINA_API_KEY="ХХХ"
```

### 4. Запуск

```bash
python main.py
```

Приложение поднимется на http://localhost:8080 (порт из `config.yaml` → `app.port`, по умолчанию `${PORT:-8080}` — можно переопределить переменной `PORT`).

При первом старте БД и схема создаются автоматически (`data/guest_ghost.db`).

### 5. Проверка

```bash
python -m pytest tests/
```

## Использование

1. **HomeDirect** — «Добавить жилище»: дом с характеристиками, ограничениями и номерным фондом.
2. **Guest Ghost** — «Добавить заявку»: приведение с тревожностью (0..1), дедлайном и требованиями.
3. **Guest Ghost** — «Подобрать жилье»: для всех свободных заявок подбираются дома (фильтр по датам + семантическое сходство + LLM-резолюция).
4. **Guest Ghost** — «Заселить в подобранное»: лист бронирования, выбор мест, конфликт мест невозможен.
5. **Guest Ghost** — иконка отчёта: отчёт по заявкам / по домам, все цифры кликабельны (переход к фильтрованным спискам).
6. **DevINFO** — «Обнулить БД» / «Предзаполнить» (5 домов + 5 заявок демо-данных).

## Деплой на Render

1. Подключить репозиторий, тип **Web Service**, Environment **Python**.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `python main.py`
4. Environment: `JINA_API_KEY`, `OLLAMA_API_KEY` (секреты), при желании `APP_STORAGE_SECRET`.
5. Free-тир: сервис засыпает через 15 мин без трафика, первый запрос после сна ~30-60с. БД не персистентная — наполняйте через «Предзаполнить» на DevINFO.

## Структура проекта

```
main.py                  # диспетчер режимов (monolith)
config.yaml              # модели, порт, api_url (поддержка ${VAR:-default})
setup.py                 # скрипт установки: БД, таблицы, миграции
backend/                 # FastAPI: db/, clients/, services/, routes/
frontend/                # NiceGUI: api/client.py, ui/ (страницы, виджеты), static/
utils/                   # logger.py (RunLogger), env.py (подстановка env)
demo_data/               # демо-данные для «Предзаполнить»
tests/                   # pytest (57)
```
