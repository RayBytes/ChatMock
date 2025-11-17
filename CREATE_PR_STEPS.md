# Шаги для создания Pull Request и релиза v1.4.0

## Шаг 1: Создайте Pull Request

**Прямая ссылка для создания PR:**
👉 https://github.com/thebtf/ChatMock/compare/main...claude/update-docs-docker-01Qptso9TSh6tW8vp4Q8LNND

### Действия:
1. Откройте ссылку выше
2. Нажмите зеленую кнопку **"Create pull request"**
3. В поле **Title** введите:
   ```
   feat: Docker PUID/PGID support and v1.4.0 release
   ```
4. В поле **Description** скопируйте содержимое из файла `PR_DESCRIPTION.md`
5. Нажмите **"Create pull request"**

## Шаг 2: Проверьте и смержите PR

1. Просмотрите изменения в PR (Files changed)
2. Убедитесь, что все выглядит правильно
3. Нажмите **"Merge pull request"**
4. Подтвердите мердж

## Шаг 3: Создайте и запушьте тег v1.4.0

После успешного мерджа выполните следующие команды **на вашем локальном компьютере**:

```bash
# Переключитесь на main и обновите
git checkout main
git pull origin main

# Создайте аннотированный тег v1.4.0
git tag -a v1.4.0 -m "Release v1.4.0: Docker improvements and comprehensive documentation

Features:
- Docker PUID/PGID support
- Multi-architecture images (amd64, arm64)
- GitHub Container Registry integration
- GPT-5.1 model support
- Comprehensive documentation

Fixes:
- Docker build compatibility (gosu)
- Improved error handling
"

# Запушьте тег в GitHub
git push origin v1.4.0
```

## Шаг 4: Проверьте автоматическую сборку

После пуша тега:

1. Перейдите в Actions: https://github.com/thebtf/ChatMock/actions
2. Вы увидите два запущенных workflow:
   - Один от мерджа в main (создаст тег `latest`)
   - Другой от тега v1.4.0 (создаст теги `v1.4.0`, `1.4.0`, `1.4`, `1`)
3. Дождитесь завершения сборки (~5-10 минут)
4. Сборка создаст образы для обеих архитектур (amd64, arm64)

## Шаг 5: Сделайте пакет публичным (опционально)

Если вы хотите, чтобы образы были публично доступны:

1. Перейдите: https://github.com/thebtf?tab=packages
2. Нажмите на пакет **"chatmock"**
3. Нажмите **"Package settings"** (справа)
4. Прокрутите до раздела **"Danger Zone"**
5. Нажмите **"Change visibility"**
6. Выберите **"Public"**
7. Подтвердите действие

## Шаг 6: Проверьте опубликованные образы

```bash
# Загрузите образ
docker pull ghcr.io/thebtf/chatmock:v1.4.0

# Проверьте мультиархитектурность
docker manifest inspect ghcr.io/thebtf/chatmock:v1.4.0

# Вы должны увидеть:
# - linux/amd64
# - linux/arm64
```

## Шаг 7: Протестируйте образ

```bash
# Создайте .env файл
cp .env.example .env

# Запустите логин
docker compose -f docker-compose.registry.yml run --rm --service-ports chatmock-login login

# Запустите сервер
docker compose -f docker-compose.registry.yml up -d chatmock

# Протестируйте API
curl -s http://localhost:8000/v1/chat/completions \
   -H 'Content-Type: application/json' \
   -d '{"model":"gpt-5","messages":[{"role":"user","content":"Hello!"}]}'
```

## Доступные теги после релиза

После завершения всех шагов, образы будут доступны по следующим тегам:

- `ghcr.io/thebtf/chatmock:latest` - последний stable билд
- `ghcr.io/thebtf/chatmock:v1.4.0` - конкретная версия с префиксом v
- `ghcr.io/thebtf/chatmock:1.4.0` - конкретная версия
- `ghcr.io/thebtf/chatmock:1.4` - минорная версия
- `ghcr.io/thebtf/chatmock:1` - мажорная версия

## Что включено в релиз v1.4.0

✅ Docker PUID/PGID support  
✅ Multi-architecture images (amd64, arm64)  
✅ GitHub Container Registry integration  
✅ Pre-built images  
✅ GPT-5.1 model support  
✅ Comprehensive documentation  
✅ Build automation scripts  
✅ Fork disclaimer  

---

**Начните с шага 1!** 🚀
