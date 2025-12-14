# Инструкции для Claude Code Web - Исправление 79 Ошибок

**ВАЖНО**: Выполнять строго по порядку. После каждого блока запускать проверку.

## ⚠️ Правила Работы

1. **НЕ КОМПИЛИРОВАТЬ** - у тебя нет dotnet
2. **Проверять каждое изменение** grep-ом
3. **Делать коммит** после каждого блока задач
4. **Если неуверен** - пропустить и написать в комментарии

## 📋 Блок 1: NovaCharacterCollectionList.Count (10 ошибок, 10 минут)

### Задача
Везде где `SettingsCharactersList.Count` добавить `.List` → `SettingsCharactersList.List.Count`

### Шаг 1.1: Найти все вхождения
```bash
grep -n "SettingsCharactersList\.Count" NovaScript.Wpf/MainWindow.xaml.cs
```

**Ожидаемый результат**: Должно найти ~10 строк

### Шаг 1.2: Заменить паттерн
```bash
sed -i 's/SettingsCharactersList\.Count/SettingsCharactersList.List.Count/g' NovaScript.Wpf/MainWindow.xaml.cs
```

### Шаг 1.3: Проверить замену
```bash
grep -n "SettingsCharactersList\.List\.Count" NovaScript.Wpf/MainWindow.xaml.cs
```

**Ожидаемый результат**: Должно найти ~10 строк с `.List.Count`

### Шаг 1.4: Проверить что не осталось старых
```bash
grep -n "SettingsCharactersList\.Count[^.]" NovaScript.Wpf/MainWindow.xaml.cs
```

**Ожидаемый результат**: Ничего не должно найти (или только в комментариях)

### Шаг 1.5: Коммит
```bash
git add NovaScript.Wpf/MainWindow.xaml.cs
git commit -m "Fix NovaCharacterCollectionList.Count - add .List accessor (10 errors)"
```

---

## 📋 Блок 2: ColorLevels Enum (12 ошибок, 15 минут)

### Задача
Добавить недостающие значения в enum ColorLevels

### Шаг 2.1: Найти файл с enum
```bash
grep -rn "enum ColorLevels" NovaScript.Wpf/
```

**Ожидаемый результат**: Должен найти файл и строку с определением enum

### Шаг 2.2: Прочитать enum
```bash
# Если нашли в файле X на строке Y:
# Read tool на этот файл, offset = Y-5, limit = 30
```

### Шаг 2.3: Добавить значения

Использовать **Edit tool** для добавления в enum ColorLevels:

```csharp
// Добавить ПЕРЕД закрывающей скобкой enum:
    CharOrphan,      // 6 errors
    BadLength,       // 6 errors
    Questionnable,   // 4 errors
    CharSpecial,     // 4 errors
    None             // 2 errors
```

**ВАЖНО**: Добавлять запятую после предыдущего последнего элемента!

### Шаг 2.4: Проверить ошибки исчезли
```bash
# Проверить что больше нет ошибок на эти значения
grep -rn "ColorLevels\.CharOrphan" NovaScript.Wpf/
grep -rn "ColorLevels\.BadLength" NovaScript.Wpf/
```

**Ожидаемый результат**: Должно находить использования (это OK)

### Шаг 2.5: Коммит
```bash
git add -A
git commit -m "Add missing ColorLevels enum values (12 errors): CharOrphan, BadLength, Questionnable, CharSpecial, None"
```

---

## 📋 Блок 3: TimelineSlider.TotalMilliseconds (4 ошибки, 10 минут)

### Задача
Исправить `.TotalMilliseconds` вызовы на TimelineSlider

### Шаг 3.1: Найти проблемные места
```bash
grep -n "timelineSlider\.TotalMilliseconds" NovaScript.Wpf/MainWindow.xaml.cs
```

**Ожидаемый результат**: ~4 строки

### Шаг 3.2: Прочитать каждую строку

Для каждой найденной строки использовать **Read tool** с offset на эту строку ±5

### Шаг 3.3: Исправить паттерны

**Паттерн A**: Если `this.timelineSlider.TotalMilliseconds` используется как значение:
```csharp
// БЫЛО:
var x = this.timelineSlider.TotalMilliseconds;

// ДОЛЖНО БЫТЬ:
var x = this.timelineSlider.Value;
```

**Паттерн B**: Если сравнение с TimeSpan:
```csharp
// БЫЛО:
if (timelineSlider.TotalMilliseconds > timeSpan.TotalMilliseconds)

// ДОЛЖНО БЫТЬ:
if (timelineSlider.Value > timeSpan.TotalMilliseconds)
```

Использовать **Edit tool** для каждой замены.

### Шаг 3.4: Проверить
```bash
grep -n "timelineSlider\.TotalMilliseconds" NovaScript.Wpf/MainWindow.xaml.cs
```

**Ожидаемый результат**: Ничего не должно найти

### Шаг 3.5: Коммит
```bash
git add NovaScript.Wpf/MainWindow.xaml.cs
git commit -m "Fix TimelineSlider.TotalMilliseconds - use .Value property (4 errors)"
```

---

## 📋 Блок 4: IsMediaLoaded Property (4 ошибки, 10 минут)

### Задача
Добавить свойство IsMediaLoaded в MainWindow

### Шаг 4.1: Найти где используется
```bash
grep -n "IsMediaLoaded()" NovaScript.Wpf/MainWindow.xaml.cs
```

**Ожидаемый результат**: ~4 строки

### Шаг 4.2: Найти где добавить свойство

Найти в MainWindow.xaml.cs секцию с другими media properties (например где IsMediaPlaying)

```bash
grep -n "private bool IsMediaPlaying" NovaScript.Wpf/MainWindow.xaml.cs
```

### Шаг 4.3: Добавить свойство

Использовать **Edit tool** - добавить ПОСЛЕ метода IsMediaPlaying:

```csharp
/// <summary>
/// Checks if media is loaded.
/// </summary>
private bool IsMediaLoaded()
{
    return _mediaService?.IsLoaded ?? false;
}
```

### Шаг 4.4: Проверить
```bash
grep -n "private bool IsMediaLoaded" NovaScript.Wpf/MainWindow.xaml.cs
```

**Ожидаемый результат**: Должно найти новый метод

### Шаг 4.5: Коммит
```bash
git add NovaScript.Wpf/MainWindow.xaml.cs
git commit -m "Add IsMediaLoaded() method wrapper (4 errors)"
```

---

## 📋 Блок 5: UI Controls - listBoxCharacters/gridScroll (28 ошибок, 30 минут)

### Задача
Закомментировать или удалить код использующий удалённые UI controls

### Шаг 5.1: Найти все вхождения listBoxCharacters
```bash
grep -n "this\.listBoxCharacters" NovaScript.Wpf/MainWindow.Hotkeys.cs
```

**Ожидаемый результат**: ~14 строк

### Шаг 5.2: Анализ каждого использования

Для КАЖДОЙ найденной строки:
1. Использовать **Read tool** с offset ±10 строк
2. Понять контекст - что делает код
3. Определить стратегию:
   - Если это установка character → использовать CharacterService
   - Если это UI обновление → можно закомментировать
   - Если это count/индекс → использовать CharacterService.GetCharacters().Count

### Шаг 5.3: Паттерн замены для character selection

**БЫЛО**:
```csharp
if (this.listBoxCharacters.Items.Count > index)
{
    this.listBoxCharacters.SelectedIndex = index;
    AddCharacterToCurrentCue();
}
```

**ДОЛЖНО БЫТЬ**:
```csharp
// Character selection via service
var charService = _characterService as CharacterService;
if (charService != null)
{
    var characters = charService.GetCharacters();
    if (index >= 0 && index < characters.Count)
    {
        var character = characters[index];
        AddCharacterToCurrentCue(character);
    }
}
```

### Шаг 5.4: Паттерн для gridScroll

```bash
grep -n "this\.gridScroll" NovaScript.Wpf/
```

**Стратегия**:
- Если это scroll операции → ЗАКОММЕНТИРОВАТЬ с пометкой `// TODO: Restore scroll functionality`
- Если это layout → ЗАКОММЕНТИРОВАТЬ

### Шаг 5.5: Применить изменения

Использовать **Edit tool** для каждого блока кода.

**ВАЖНО**: Если не уверен в замене - ЗАКОММЕНТИРУЙ блок с пометкой:
```csharp
// FIXME: UI control removed - needs reimplementation
// Old code:
// this.listBoxCharacters...
```

### Шаг 5.6: Проверка
```bash
grep -n "this\.listBoxCharacters[^/]" NovaScript.Wpf/MainWindow.Hotkeys.cs
grep -n "this\.gridScroll[^/]" NovaScript.Wpf/
```

**Ожидаемый результат**: Не должно найти активных вызовов (только закомментированные - это OK)

### Шаг 5.7: Коммит
```bash
git add -A
git commit -m "Remove/comment obsolete UI controls: listBoxCharacters, gridScroll (28 errors)

- Replaced character selection with CharacterService where possible
- Commented scroll operations with FIXME markers
- All UI control references removed or commented"
```

---

## 📋 Блок 6: Xceed DOCX API - Novacode Namespace (8 ошибок, 20 минут)

### Задача
Заменить старое пространство имён Novacode на Xceed

### Шаг 6.1: Найти файлы с using Novacode
```bash
grep -rn "using Novacode" NovaScript.Wpf/
```

**Ожидаемый результат**: ~8 файлов

### Шаг 6.2: Для каждого файла

Использовать **Edit tool**:

```csharp
// БЫЛО:
using Novacode;

// ДОЛЖНО БЫТЬ:
using Xceed.Words.NET;
using Xceed.Document.NET;
```

### Шаг 6.3: Проверка типов

После замены using, проверить нужны ли дополнительные изменения:

```bash
# Найти использования типов из Novacode
grep -n "Novacode\." NovaScript.Wpf/Library/Logic/Exporter.cs
```

Если находит - заменить префикс:
- `Novacode.DocX` → `DocX` (уже импортирован)
- `Novacode.Table` → `Table`
- и т.д.

### Шаг 6.4: Проверить
```bash
grep -rn "using Novacode" NovaScript.Wpf/
```

**Ожидаемый результат**: Ничего не должно найти

### Шаг 6.5: Коммит
```bash
git add -A
git commit -m "Replace Novacode namespace with Xceed.Words.NET (8 errors)"
```

---

## 📋 Блок 7: IDocxParagraph.InsertText (10 ошибок, 30 минут)

### Задача
Заменить InsertText на правильный Xceed API

### Шаг 7.1: Найти все вызовы
```bash
grep -n "\.InsertText(" NovaScript.Wpf/Library/Logic/Exporter.cs
```

**Ожидаемый результат**: ~10 строк

### Шаг 7.2: Понять паттерн

Прочитать несколько примеров использования **Read tool**.

Старый API (Novacode):
```csharp
paragraph.InsertText("text", formatting);
```

Новый API (Xceed):
```csharp
paragraph.Append("text").Font(formatting.FontFamily).FontSize(formatting.Size);
```

### Шаг 7.3: Стратегия замены

**Паттерн A - простой текст**:
```csharp
// БЫЛО:
paragraph.InsertText(text);

// ДОЛЖНО БЫТЬ:
paragraph.Append(text);
```

**Паттерн B - с форматированием**:
```csharp
// БЫЛО:
paragraph.InsertText(text, formatting);

// ДОЛЖНО БЫТЬ:
var run = paragraph.Append(text);
if (formatting.FontFamily != null)
    run.Font(formatting.FontFamily);
if (formatting.Size.HasValue)
    run.FontSize(formatting.Size.Value);
if (formatting.Bold)
    run.Bold();
```

### Шаг 7.4: Применить замены

Использовать **Edit tool** для каждого вызова InsertText.

**ЕСЛИ ПАТТЕРН СЛОЖНЫЙ** - оставь комментарий:
```csharp
// TODO: Xceed API - complex formatting pattern
// Original: paragraph.InsertText(text, formatting);
paragraph.Append(text); // Basic implementation
```

### Шаг 7.5: Проверка
```bash
grep -n "\.InsertText(" NovaScript.Wpf/Library/Logic/Exporter.cs
```

**Ожидаемый результат**: Ничего не должно найти (или только в комментариях)

### Шаг 7.6: Коммит
```bash
git add NovaScript.Wpf/Library/Logic/Exporter.cs
git commit -m "Replace IDocxParagraph.InsertText with Xceed Append API (10 errors)

- Simple InsertText → Append
- Formatted InsertText → Append with formatting methods
- Complex patterns marked with TODO for manual review"
```

---

## 📋 Блок 8: Остальные Ошибки (7 ошибок, 20 минут)

### Шаг 8.1: IDocumentService.CurrentFilePath (4 ошибки)

```bash
grep -n "\.CurrentFilePath" NovaScript.Wpf/
```

**Решение**: Заменить на альтернативу:
```csharp
// БЫЛО:
var path = _documentService.CurrentFilePath;

// ДОЛЖНО БЫТЬ:
var path = App.NSettings?.GeneralSettings?.LoadedDocument ?? string.Empty;
```

### Шаг 8.2: IHotkeyManager Type (4 ошибки)

```bash
grep -n "IHotkeyManager" NovaScript.Wpf/
```

**Решение**: Заменить тип на правильный:
```csharp
// БЫЛО:
IHotkeyManager

// ДОЛЖНО БЫТЬ:
NovaScript.Library.Hotkeys.Services.IHotkeyService
```

### Шаг 8.3: Прочие единичные ошибки

Для каждой оставшейся ошибки:
1. Найти строку через grep
2. Прочитать контекст
3. Применить логичное исправление
4. Если не очевидно - ЗАКОММЕНТИРОВАТЬ с FIXME

### Шаг 8.4: Коммит
```bash
git add -A
git commit -m "Fix remaining misc errors (7 errors): CurrentFilePath, IHotkeyManager, etc."
```

---

## ✅ Финальная Проверка

### Шаг 9.1: Проверить все изменения
```bash
git status
git diff HEAD~8 --stat
```

**Ожидаемый результат**: Должно показать изменённые файлы из всех блоков

### Шаг 9.2: Проверить что не сломали существующий код

```bash
# Проверить что не появились новые проблемы
grep -rn "TODO\|FIXME" NovaScript.Wpf/ | wc -l
```

Запиши количество TODO/FIXME в комментарий коммита.

### Шаг 9.3: Создать summary
```bash
git log --oneline HEAD~8..HEAD > /tmp/commits.txt
cat /tmp/commits.txt
```

### Шаг 9.4: Финальный коммит
```bash
git add -A
git commit -m "Complete web session: Fixed 79 build errors

Blocks completed:
1. NovaCharacterCollectionList.Count (10 errors)
2. ColorLevels enum values (12 errors)
3. TimelineSlider.TotalMilliseconds (4 errors)
4. IsMediaLoaded method (4 errors)
5. UI controls removal (28 errors)
6. Novacode namespace (8 errors)
7. IDocxParagraph.InsertText (10 errors)
8. Misc fixes (7 errors)

Total: 83 errors fixed (some overlap with previous work)
Ready for build verification."
```

---

## 📝 Отчёт для Возврата

Создай файл `WEB_SESSION_REPORT.md` с:

```markdown
# Web Session Report

## Completed
- [x] Block 1: NovaCharacterCollectionList.Count
- [x] Block 2: ColorLevels enum
- [x] Block 3: TimelineSlider.TotalMilliseconds
- [x] Block 4: IsMediaLoaded
- [x] Block 5: UI controls
- [x] Block 6: Novacode namespace
- [x] Block 7: IDocxParagraph.InsertText
- [x] Block 8: Misc errors

## Issues Encountered
[Список проблем если были]

## Manual Review Needed
[Список мест с TODO/FIXME метками]

## Files Modified
[git diff --name-only HEAD~8]

## Ready for Build Test
Yes/No - [пояснение]
```

---

## 🚨 Если Что-то Пошло Не Так

### Откат блока
```bash
git reset --soft HEAD~1  # откатить последний коммит
git restore <file>       # откатить изменения файла
```

### Просмотр изменений
```bash
git diff HEAD~1 <file>   # посмотреть что изменилось
```

### Пауза и запрос помощи
Если блок слишком сложный - оставь комментарий в коммите:
```
[PAUSED] Block X - requires architectural decision
Reason: [детали]
```

---

## 📊 Ожидаемый Результат

После выполнения всех блоков:
- **9 коммитов** (8 блоков + финальный)
- **~79 ошибок исправлено**
- **Готово к проверке build**
- **Чистое рабочее дерево**

Удачи! 🚀
