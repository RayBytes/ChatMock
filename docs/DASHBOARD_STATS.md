# Dashboard Statistics System

## Overview

ChatMock теперь собирает **реальную статистику** по всем запросам через API. Никаких заглушек или мок-данных - все метрики основаны на фактических запросах к системе.

## Собираемые метрики

### Общая статистика
- **total_requests** - общее количество запросов
- **total_successful** - количество успешных запросов
- **total_failed** - количество неудачных запросов
- **total_tokens** - общее количество токенов
- **total_prompt_tokens** - токены в запросах
- **total_completion_tokens** - токены в ответах
- **avg_response_time** - среднее время ответа (секунды)
- **total_response_time** - суммарное время всех ответов
- **first_request** - время первого запроса (ISO 8601)
- **last_request** - время последнего запроса (ISO 8601)

### Разбивка по моделям
- **requests_by_model** - количество запросов по каждой модели
- **tokens_by_model** - использование токенов по каждой модели:
  - `total` - всего токенов
  - `prompt` - токены в запросах
  - `completion` - токены в ответах

### Разбивка по эндпоинтам
- **requests_by_endpoint** - количество запросов по каждому endpoint:
  - `openai/chat/completions` - OpenAI chat (non-streaming)
  - `openai/chat/completions/stream` - OpenAI chat (streaming)
  - `openai/completions` - OpenAI text completions (non-streaming)
  - `openai/completions/stream` - OpenAI text completions (streaming)
  - `ollama/chat` - Ollama chat (non-streaming)
  - `ollama/chat/stream` - Ollama chat (streaming)

### Разбивка по датам
- **requests_by_date** - количество запросов по дням (формат YYYY-MM-DD)

### История запросов
- **recent_requests** - последние 100 запросов с полной информацией:
  - `timestamp` - время запроса
  - `model` - использованная модель
  - `endpoint` - endpoint запроса
  - `success` - успешность запроса (true/false)
  - `prompt_tokens` - токены в запросе
  - `completion_tokens` - токены в ответе
  - `total_tokens` - всего токенов
  - `response_time` - время ответа (секунды)
  - `error` - сообщение об ошибке (если есть)

## Хранение данных

Все статистики сохраняются в файл `stats.json` в директории `CHATGPT_LOCAL_HOME` (по умолчанию `~/.chatgpt-local/`).

Формат файла:
```json
{
  "total_requests": 42,
  "total_successful": 40,
  "total_failed": 2,
  "total_tokens": 1234,
  "total_prompt_tokens": 456,
  "total_completion_tokens": 778,
  "avg_response_time": 1.23,
  "total_response_time": 51.66,
  "first_request": "2025-01-15T10:30:00.123456",
  "last_request": "2025-01-15T15:45:30.789012",
  "requests_by_model": {
    "gpt-5": 25,
    "gpt-5-codex": 15,
    "gpt-5.1": 2
  },
  "tokens_by_model": {
    "gpt-5": {
      "total": 800,
      "prompt": 300,
      "completion": 500
    }
  },
  "requests_by_endpoint": {
    "openai/chat/completions": 30,
    "ollama/chat": 12
  },
  "requests_by_date": {
    "2025-01-15": 42
  },
  "recent_requests": [
    {
      "timestamp": "2025-01-15T15:45:30.789012",
      "model": "gpt-5",
      "endpoint": "openai/chat/completions",
      "success": true,
      "prompt_tokens": 15,
      "completion_tokens": 25,
      "total_tokens": 40,
      "response_time": 1.234,
      "error": null
    }
  ]
}
```

## API Endpoints

### GET /api/stats
Возвращает полную статистику, включая информацию о rate limits.

**Пример ответа:**
```json
{
  "total_requests": 42,
  "total_successful": 40,
  "total_failed": 2,
  "requests_by_model": {...},
  "tokens_by_model": {...},
  "requests_by_endpoint": {...},
  "requests_by_date": {...},
  "avg_response_time": 1.23,
  "last_request": "2025-01-15T15:45:30.789012",
  "first_request": "2025-01-15T10:30:00.123456",
  "recent_requests": [...],
  "rate_limits": {
    "captured_at": "2025-01-15T15:45:30.789012",
    "primary": {
      "used_percent": 45.2,
      "resets_in_seconds": 3600,
      "reset_at": "2025-01-15T16:45:30.789012"
    }
  }
}
```

### GET /api/request-history?limit=N
Возвращает историю последних N запросов (по умолчанию 50, максимум 100).

**Параметры:**
- `limit` (опционально) - количество запросов для возврата (1-100)

**Пример ответа:**
```json
{
  "requests": [
    {
      "timestamp": "2025-01-15T15:45:30.789012",
      "model": "gpt-5",
      "endpoint": "openai/chat/completions",
      "success": true,
      "prompt_tokens": 15,
      "completion_tokens": 25,
      "total_tokens": 40,
      "response_time": 1.234,
      "error": null
    }
  ],
  "total_count": 100
}
```

## Сбор статистики по endpoint'ам

### OpenAI Chat Completions
- **Endpoint:** `/v1/chat/completions`
- **Собираемые данные:**
  - Модель из запроса
  - Количество токенов из usage object
  - Время выполнения запроса
  - Ошибки (если есть)
  - Поддержка streaming и non-streaming режимов

### OpenAI Text Completions
- **Endpoint:** `/v1/completions`
- **Собираемые данные:** аналогично chat completions

### Ollama Chat
- **Endpoint:** `/api/chat`
- **Собираемые данные:**
  - Модель из запроса
  - Примерное количество токенов (на основе fake_eval данных)
  - Время выполнения запроса
  - Ошибки (если есть)
  - Поддержка streaming и non-streaming режимов

**Примечание:** Ollama API не предоставляет точные данные о токенах, поэтому используются приблизительные значения из `_OLLAMA_FAKE_EVAL`.

## Тестирование

Для тестирования системы сбора статистики используйте скрипт `test_stats.py`:

```bash
# Убедитесь, что сервер запущен
python chatmock.py serve

# В другом терминале запустите тест
python test_stats.py
```

Скрипт выполнит несколько тестовых запросов и покажет собранную статистику.

## Обратная совместимость

Система полностью обратно совместима со старым форматом `stats.json`. При загрузке существующего файла все отсутствующие поля будут автоматически добавлены с значениями по умолчанию.

## Производительность

- Запись статистики выполняется синхронно после каждого запроса
- Файл `stats.json` перезаписывается полностью при каждом обновлении
- История запросов ограничена последними 100 записями для контроля размера файла
- В среднем операция записи занимает < 10ms

## Рекомендации

1. **Мониторинг размера файла:** Периодически проверяйте размер `stats.json`. Если файл становится слишком большим, можно вручную очистить `recent_requests` или сбросить статистику.

2. **Резервное копирование:** Рекомендуется периодически создавать резервные копии файла статистики для анализа исторических данных.

3. **Анализ производительности:** Используйте `avg_response_time` для мониторинга производительности системы.

4. **Отслеживание ошибок:** Проверяйте `total_failed` и `recent_requests` для выявления проблем с API.

## Будущие улучшения

Возможные направления развития:
- Экспорт статистики в CSV/JSON
- Графики использования по времени
- Алерты при превышении лимитов
- Интеграция с внешними системами мониторинга
- Детальная статистика по function calling
- Отслеживание использования reasoning features
